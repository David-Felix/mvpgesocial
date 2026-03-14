import os
import glob
import shutil
import subprocess
import tempfile
from datetime import timedelta

from django.core.management.base import BaseCommand
from django.utils import timezone

from beneficios.models import BackupConfig, BackupHistorico, BackupLog

BACKUP_LOCAL_DIR = '/var/www/sistema_beneficios_data/backups'


class Command(BaseCommand):
    help = 'Executa backup do sistema GeSocial'
    
    def add_arguments(self, parser):
        parser.add_argument('--backup-id', type=int, help='ID do BackupHistorico (uso interno)')
        parser.add_argument('--tipo', type=str, default='manual', choices=['manual', 'automatico'])
        parser.add_argument('--tipo-backup', type=str, required=True, choices=['banco', 'documentos'])
    
    def handle(self, *args, **options):
        config = BackupConfig.get_config()
        tipo_backup = options['tipo_backup']
        
        # Limpar backups travados
        stale = BackupHistorico.objects.filter(
            status='executando',
            data_inicio__lt=timezone.now() - timedelta(hours=1)
        )
        for s in stale:
            s.status = 'erro'
            s.data_fim = timezone.now()
            s.save(update_fields=['status', 'data_fim'])
            BackupLog.objects.create(
                backup=s, etapa='fim', status='erro',
                mensagem='Marcado como erro: executando há mais de 1 hora'
            )
        
        # Timestamp e nomes
        timestamp = timezone.localtime()
        ts_arquivo = timestamp.strftime('%Y-%m-%d-%H-%M-%S')
        ts_senha = timestamp.strftime('%Y%m%d%H%M%S')
        
        prefixo = 'BK_DB' if tipo_backup == 'banco' else 'BK_DOC'
        arquivo_base = f'{prefixo}_{ts_arquivo}'
        arquivo_final = f'{arquivo_base}.tar.zst.gpg'
        senha = f'G3social{ts_senha}'
        
        # Criar ou recuperar registro
        if options['backup_id']:
            try:
                backup = BackupHistorico.objects.get(id=options['backup_id'])
                backup.arquivo_nome = arquivo_final
                backup.save(update_fields=['arquivo_nome'])
            except BackupHistorico.DoesNotExist:
                self.stderr.write('Backup ID não encontrado.')
                return
        else:
            backup = BackupHistorico.objects.create(
                tipo=options['tipo'],
                tipo_backup=tipo_backup,
                itens=tipo_backup,
                status='executando',
                arquivo_nome=arquivo_final,
            )
        
        # Verificar concorrência
        if BackupHistorico.objects.filter(status='executando').exclude(id=backup.id).exists():
            self._log(backup, 'inicio', 'erro', 'Outro backup já está em execução.')
            self._finalizar_erro(backup)
            return
        
        # Garantir diretório local
        os.makedirs(BACKUP_LOCAL_DIR, exist_ok=True)
        
        # Diretório temporário
        tmp_dir = tempfile.mkdtemp(prefix='gesocial_bkp_')
        conteudo_dir = os.path.join(tmp_dir, 'conteudo')
        os.makedirs(conteudo_dir)
        
        try:
            label = 'Banco de Dados' if tipo_backup == 'banco' else 'Documentos'
            self._log(backup, 'inicio', 'sucesso', f'Backup de {label} iniciado')
            
            # ═══ GERAR CONTEÚDO ═══
            if tipo_backup == 'banco':
                sucesso = self._gerar_dump_banco(backup, conteudo_dir)
            else:
                sucesso = self._gerar_tar_documentos(backup, conteudo_dir)
            
            if not sucesso:
                return
            
            # ═══ COMPRIMIR COM ZSTD ═══
            self._log(backup, 'comprimir', 'executando', 'Comprimindo com zstd...')
            try:
                tar_path = os.path.join(tmp_dir, f'{arquivo_base}.tar')
                subprocess.run(
                    ['tar', '-cf', tar_path, '-C', conteudo_dir, '.'],
                    check=True, capture_output=True, timeout=600
                )
                
                zst_path = f'{tar_path}.zst'
                subprocess.run(
                    ['zstd', '--rm', '-q', '-3', tar_path, '-o', zst_path],
                    check=True, capture_output=True, timeout=600
                )
                
                tamanho = os.path.getsize(zst_path)
                self._log(backup, 'comprimir', 'sucesso', f'Comprimido ({self._fmt(tamanho)})')
            except subprocess.TimeoutExpired:
                self._log(backup, 'comprimir', 'erro', 'Timeout na compressão')
                self._finalizar_erro(backup)
                return
            except subprocess.CalledProcessError as e:
                self._log(backup, 'comprimir', 'erro', f'Falha: {e.stderr.decode()[:500]}')
                self._finalizar_erro(backup)
                return
            
            # ═══ CRIPTOGRAFAR COM GPG ═══
            self._log(backup, 'criptografar', 'executando', 'Criptografando...')
            try:
                gpg_path = os.path.join(tmp_dir, arquivo_final)
                subprocess.run([
                    'gpg', '--batch', '--yes',
                    '--passphrase', senha,
                    '--symmetric', '--cipher-algo', 'AES256',
                    '--pinentry-mode', 'loopback',
                    '-o', gpg_path, zst_path
                ], check=True, capture_output=True, timeout=600)
                
                os.remove(zst_path)
                tamanho_final = os.path.getsize(gpg_path)
                self._log(backup, 'criptografar', 'sucesso',
                         f'Criptografado ({self._fmt(tamanho_final)})')
            except subprocess.TimeoutExpired:
                self._log(backup, 'criptografar', 'erro', 'Timeout na criptografia')
                self._finalizar_erro(backup)
                return
            except subprocess.CalledProcessError as e:
                self._log(backup, 'criptografar', 'erro', f'Falha: {e.stderr.decode()[:500]}')
                self._finalizar_erro(backup)
                return
            
            # ═══ COPIAR LOCAL ═══
            self._log(backup, 'copiar_local', 'executando', 'Salvando cópia local...')
            try:
                local_path = os.path.join(BACKUP_LOCAL_DIR, arquivo_final)
                shutil.copy2(gpg_path, local_path)
                self._log(backup, 'copiar_local', 'sucesso',
                         f'Cópia local salva ({self._fmt(tamanho_final)})')
            except Exception as e:
                self._log(backup, 'copiar_local', 'erro', f'Falha: {str(e)[:500]}')
                self._finalizar_erro(backup)
                return
            
            # ═══ ENVIAR GOOGLE DRIVE ═══
            self._log(backup, 'enviar', 'executando', f'Enviando para {config.rclone_destino}...')
            try:
                subprocess.run(
                    ['rclone', 'copy', gpg_path, config.rclone_destino],
                    check=True, capture_output=True, timeout=1800
                )
                self._log(backup, 'enviar', 'sucesso', 'Enviado para Google Drive')
            except subprocess.TimeoutExpired:
                self._log(backup, 'enviar', 'erro', 'Timeout: envio demorou mais de 30 minutos')
                self._finalizar_erro(backup)
                return
            except subprocess.CalledProcessError as e:
                self._log(backup, 'enviar', 'erro', f'Falha: {e.stderr.decode()[:500]}')
                self._finalizar_erro(backup)
                return
            
            # ═══ RETENÇÃO ═══
            if tipo_backup == 'banco':
                versoes_nuvem = config.versoes_nuvem_db
                versoes_local = config.versoes_local_db
            else:
                versoes_nuvem = config.versoes_nuvem_doc
                versoes_local = config.versoes_local_doc
            
            if versoes_nuvem > 0:
                self._log(backup, 'retencao_nuvem', 'executando',
                         f'Mantendo {versoes_nuvem} versões na nuvem...')
                try:
                    removidos = self._retencao_nuvem(config, prefixo, versoes_nuvem)
                    self._log(backup, 'retencao_nuvem', 'sucesso',
                             f'{removidos} versões antigas removidas')
                except Exception as e:
                    self._log(backup, 'retencao_nuvem', 'erro', f'Falha: {str(e)[:500]}')
            
            if versoes_local > 0:
                self._log(backup, 'retencao_local', 'executando',
                         f'Mantendo {versoes_local} versões locais...')
                try:
                    removidos = self._retencao_local(prefixo, versoes_local)
                    self._log(backup, 'retencao_local', 'sucesso',
                             f'{removidos} versões antigas removidas')
                except Exception as e:
                    self._log(backup, 'retencao_local', 'erro', f'Falha: {str(e)[:500]}')
            
            # ═══ SUCESSO ═══
            backup.status = 'sucesso'
            backup.tamanho_bytes = tamanho_final
            backup.data_fim = timezone.now()
            backup.save(update_fields=['status', 'tamanho_bytes', 'data_fim'])
            
            self._log(backup, 'fim', 'sucesso', 'Backup concluído com sucesso!')
            self.stdout.write(self.style.SUCCESS(f'Backup concluído: {arquivo_final}'))
        
        except Exception as e:
            self._log(backup, 'fim', 'erro', f'Erro inesperado: {str(e)[:500]}')
            self._finalizar_erro(backup)
        
        finally:
            shutil.rmtree(tmp_dir, ignore_errors=True)
    
    def _gerar_dump_banco(self, backup, conteudo_dir):
        """Gera dump do PostgreSQL"""
        self._log(backup, 'dump_banco', 'executando', 'Gerando dump do banco de dados...')
        try:
            dump_path = os.path.join(conteudo_dir, 'banco.sql')
            env = os.environ.copy()
            env['PGPASSFILE'] = '/var/www/.pgpass'
            result = subprocess.run(
                ['pg_dump', '-U', 'gesocial_backup', '-h', 'localhost', 'beneficios_db'],
                capture_output=True, check=True, timeout=600, env=env
            )
            with open(dump_path, 'wb') as f:
                f.write(result.stdout)
            
            tamanho = os.path.getsize(dump_path)
            self._log(backup, 'dump_banco', 'sucesso', f'Dump concluído ({self._fmt(tamanho)})')
            return True
        except subprocess.TimeoutExpired:
            self._log(backup, 'dump_banco', 'erro', 'Timeout: dump demorou mais de 10 minutos')
            self._finalizar_erro(backup)
            return False
        except subprocess.CalledProcessError as e:
            self._log(backup, 'dump_banco', 'erro', f'Falha: {e.stderr.decode()[:500]}')
            self._finalizar_erro(backup)
            return False
    
    def _gerar_tar_documentos(self, backup, conteudo_dir):
        """Compacta diretório de documentos"""
        self._log(backup, 'compactar_docs', 'executando', 'Compactando documentos...')
        try:
            media_path = '/var/www/sistema_beneficios_data/media'
            if os.path.exists(media_path) and os.listdir(media_path):
                docs_tar = os.path.join(conteudo_dir, 'documentos.tar')
                subprocess.run(
                    ['tar', '-cf', docs_tar, '-C', media_path, '.'],
                    check=True, capture_output=True, timeout=600
                )
                tamanho = os.path.getsize(docs_tar)
                self._log(backup, 'compactar_docs', 'sucesso',
                         f'Compactados ({self._fmt(tamanho)})')
                return True
            else:
                self._log(backup, 'compactar_docs', 'erro', 'Nenhum documento encontrado.')
                self._finalizar_erro(backup)
                return False
        except subprocess.TimeoutExpired:
            self._log(backup, 'compactar_docs', 'erro', 'Timeout ao compactar documentos')
            self._finalizar_erro(backup)
            return False
        except subprocess.CalledProcessError as e:
            self._log(backup, 'compactar_docs', 'erro', f'Falha: {e.stderr.decode()[:500]}')
            self._finalizar_erro(backup)
            return False
    
    def _retencao_nuvem(self, config, prefixo, versoes):
        """Remove backups antigos da nuvem por prefixo"""
        result = subprocess.run(
            ['rclone', 'lsf', '--files-only', config.rclone_destino],
            capture_output=True, text=True, timeout=60
        )
        
        if result.returncode != 0 or not result.stdout.strip():
            return 0
        
        arquivos = sorted([
            f.strip() for f in result.stdout.strip().split('\n')
            if f.strip().startswith(f'{prefixo}_') and f.strip().endswith('.gpg')
        ])
        
        if len(arquivos) <= versoes:
            return 0
        
        para_remover = arquivos[:len(arquivos) - versoes]
        for arq in para_remover:
            subprocess.run(
                ['rclone', 'deletefile', '--drive-use-trash=false',
                 f'{config.rclone_destino}/{arq}'],
                capture_output=True, timeout=60
            )
        
        return len(para_remover)
    
    def _retencao_local(self, prefixo, versoes):
        """Remove backups antigos locais por prefixo"""
        arquivos = sorted(glob.glob(os.path.join(BACKUP_LOCAL_DIR, f'{prefixo}_*.gpg')))
        
        removidos = 0
        if len(arquivos) > versoes:
            para_remover = arquivos[:len(arquivos) - versoes]
            for arq in para_remover:
                os.remove(arq)
                removidos += 1
        
        return removidos
    
    def _log(self, backup, etapa, status, mensagem):
        BackupLog.objects.create(
            backup=backup, etapa=etapa,
            status=status, mensagem=mensagem,
        )
        if status == 'erro':
            self.stderr.write(f'[ERRO] {mensagem}')
        else:
            self.stdout.write(f'[{etapa.upper()}] {mensagem}')
    
    def _finalizar_erro(self, backup):
        backup.status = 'erro'
        backup.data_fim = timezone.now()
        backup.save(update_fields=['status', 'data_fim'])
    
    def _fmt(self, bytes_size):
        if bytes_size < 1024:
            return f'{bytes_size} B'
        elif bytes_size < 1024 * 1024:
            return f'{bytes_size / 1024:.1f} KB'
        elif bytes_size < 1024 * 1024 * 1024:
            return f'{bytes_size / (1024 * 1024):.1f} MB'
        else:
            return f'{bytes_size / (1024 * 1024 * 1024):.2f} GB'