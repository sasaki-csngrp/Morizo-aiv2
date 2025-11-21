"""
Morizo AI v2 - Logging Configuration

This module provides centralized logging configuration for the entire application.
Implements hierarchical logging with file rotation and console output.
"""

import logging
import logging.handlers
import os
import shutil
from pathlib import Path
from typing import Optional
from datetime import datetime
import time


def jst_time(*args):
    """JST（日本時間）を返すconverter関数（システムのタイムゾーンを使用）"""
    # システムのタイムゾーンがJSTに設定されているため、time.localtime()はJSTを返す
    return time.localtime()


class AlignedFormatter(logging.Formatter):
    """Custom formatter that aligns logger names and log levels"""
    
    def __init__(self, fmt=None, datefmt=None):
        super().__init__(fmt, datefmt)
        # JSTタイムゾーンを使用するようにconverterを設定
        self.converter = jst_time
        self.logger_name_width = 30  # Fixed width for logger names
        self.level_name_width = 5    # Fixed width for log levels
    
    def format(self, record):
        # Format logger name with padding/truncation
        logger_name = record.name
        if len(logger_name) > self.logger_name_width:
            logger_name = logger_name[:self.logger_name_width]
        else:
            logger_name = logger_name.ljust(self.logger_name_width)
        
        # Format level name with padding
        level_name = record.levelname.ljust(self.level_name_width)
        
        # Create aligned format
        aligned_format = f'%(asctime)s - {logger_name} - {level_name} - %(message)s'
        
        # Create temporary formatter with aligned format
        temp_formatter = logging.Formatter(aligned_format, self.datefmt)
        # JSTタイムゾーンを使用するようにconverterを設定
        temp_formatter.converter = jst_time
        return temp_formatter.format(record)


class LoggingConfig:
    """Centralized logging configuration for Morizo AI v2"""
    
    def __init__(self):
        # 環境変数からログファイルパスを取得
        log_file = os.getenv('LOG_FILE', 'morizo_ai.log')
        log_dir = os.getenv('LOG_DIR', '.')
        
        # ディレクトリが指定されている場合は結合
        if log_dir != '.':
            # ディレクトリが存在しない場合は作成
            os.makedirs(log_dir, exist_ok=True)
            self.log_file = os.path.join(log_dir, os.path.basename(log_file))
        else:
            self.log_file = log_file
        
        # エラーログファイルパスを生成（通常ログファイル名から生成）
        log_file_base = os.path.basename(log_file)
        if log_file_base.endswith('.log'):
            error_log_file = log_file_base.replace('.log', '_error.log')
        else:
            error_log_file = f"{log_file_base}_error.log"
        
        if log_dir != '.':
            self.error_log_file = os.path.join(log_dir, error_log_file)
        else:
            self.error_log_file = error_log_file
        
        # バックアップファイル名を生成
        self.backup_file = f"{self.log_file}.1"
        
        self.max_file_size = 10 * 1024 * 1024  # 10MB
        self.backup_count = 5
        self.log_format = '%(asctime)s - %(name)s - %(levelname)s - %(message)s'
        self.date_format = '%Y-%m-%d %H:%M:%S'
        
    def setup_logging(self, log_level: str = "INFO", initialize: bool = True) -> logging.Logger:
        """
        Setup centralized logging configuration
        
        Args:
            log_level: Logging level (DEBUG, INFO, WARNING, ERROR)
            initialize: Whether to initialize (create backup) log files
            
        Returns:
            Configured root logger
        """
        # Create root logger
        root_logger = logging.getLogger('morizo_ai')
        root_logger.setLevel(getattr(logging, log_level.upper()))
        
        # Clear existing handlers to avoid duplicates
        root_logger.handlers.clear()
        
        # Setup file handler with rotation
        self._setup_file_handler(root_logger, log_level, initialize)
        
        # Setup error file handler for ERROR/CRITICAL logs
        self._setup_error_file_handler(root_logger, initialize)
        
        # Setup console handler for development
        self._setup_console_handler(root_logger, log_level)
        
        # Prevent propagation to avoid duplicate logs
        root_logger.propagate = False
        
        root_logger.debug(f"🔧 [LOGGING] ロギング設定が完了しました (ログレベル: {log_level})")
        return root_logger
    
    def _setup_file_handler(self, logger: logging.Logger, log_level: str, initialize: bool = True) -> None:
        """Setup file handler with rotation"""
        try:
            # Create backup if log file exists and initialization is requested
            # 環境変数LOG_INITIALIZE_BACKUPで制御可能（デフォルト: true）
            if initialize:
                should_backup = os.getenv('LOG_INITIALIZE_BACKUP', 'true').lower() == 'true'
                if should_backup:
                    self._create_log_backup()
            
            # Pythonのローテーションを使用するかどうか（環境変数で制御）
            # 本番環境でlogrotateを使用する場合はfalseに設定
            use_python_rotation = os.getenv('LOG_USE_PYTHON_ROTATION', 'true').lower() == 'true'
            
            if use_python_rotation:
                # Create rotating file handler (Python側でローテーション)
                file_handler = logging.handlers.RotatingFileHandler(
                    filename=self.log_file,
                    maxBytes=self.max_file_size,
                    backupCount=self.backup_count,
                    encoding='utf-8'
                )
                logger.debug(f"📁 [LOGGING] Pythonローテーション有効: {self.log_file}")
            else:
                # Create simple file handler (logrotateを使用する場合)
                file_handler = logging.FileHandler(
                    filename=self.log_file,
                    encoding='utf-8'
                )
                logger.debug(f"📁 [LOGGING] logrotate使用（Pythonローテーション無効）: {self.log_file}")
            
            file_handler.setLevel(getattr(logging, log_level.upper()))
            
            # Set aligned formatter
            formatter = AlignedFormatter(
                fmt=self.log_format,
                datefmt=self.date_format
            )
            file_handler.setFormatter(formatter)
            
            logger.addHandler(file_handler)
            logger.debug(f"📁 [LOGGING] ファイルハンドラー設定完了: {self.log_file}")
            
        except Exception as e:
            logger.error(f"❌ [LOGGING] ファイルハンドラー設定エラー: {e}")
    
    def _setup_console_handler(self, logger: logging.Logger, log_level: str) -> None:
        """Setup console handler for development"""
        try:
            console_handler = logging.StreamHandler()
            console_handler.setLevel(getattr(logging, log_level.upper()))
            
            # Set aligned formatter
            formatter = AlignedFormatter(
                fmt=self.log_format,
                datefmt=self.date_format
            )
            console_handler.setFormatter(formatter)
            
            logger.addHandler(console_handler)
            logger.debug("🖥️ [LOGGING] コンソールハンドラー設定完了")
            
        except Exception as e:
            logger.error(f"❌ [LOGGING] コンソールハンドラー設定エラー: {e}")
    
    def _setup_error_file_handler(self, logger: logging.Logger, initialize: bool = True) -> None:
        """Setup error file handler for ERROR/CRITICAL logs"""
        try:
            # Pythonのローテーションを使用するかどうか（環境変数で制御）
            # 本番環境でlogrotateを使用する場合はfalseに設定
            use_python_rotation = os.getenv('LOG_USE_PYTHON_ROTATION', 'true').lower() == 'true'
            
            if use_python_rotation:
                # Create rotating file handler for errors (Python側でローテーション)
                error_file_handler = logging.handlers.RotatingFileHandler(
                    filename=self.error_log_file,
                    maxBytes=self.max_file_size,
                    backupCount=self.backup_count,
                    encoding='utf-8'
                )
                logger.debug(f"📁 [LOGGING] エラーログ: Pythonローテーション有効: {self.error_log_file}")
            else:
                # Create simple file handler for errors (logrotateを使用する場合)
                error_file_handler = logging.FileHandler(
                    filename=self.error_log_file,
                    encoding='utf-8'
                )
                logger.debug(f"📁 [LOGGING] エラーログ: logrotate使用（Pythonローテーション無効）: {self.error_log_file}")
            
            # Only capture ERROR and CRITICAL logs
            error_file_handler.setLevel(logging.ERROR)
            
            # Set aligned formatter
            formatter = AlignedFormatter(
                fmt=self.log_format,
                datefmt=self.date_format
            )
            error_file_handler.setFormatter(formatter)
            
            logger.addHandler(error_file_handler)
            logger.debug(f"📁 [LOGGING] エラーログファイルハンドラー設定完了: {self.error_log_file}")
            
        except Exception as e:
            logger.error(f"❌ [LOGGING] エラーログファイルハンドラー設定エラー: {e}")
    
    def _create_log_backup(self) -> None:
        """Create backup of existing log file"""
        if os.path.exists(self.log_file):
            try:
                shutil.move(self.log_file, self.backup_file)
                print(f"📦 [LOGGING] ログファイルをバックアップ: {self.log_file} → {self.backup_file}")
            except Exception as e:
                print(f"⚠️ [LOGGING] バックアップ作成エラー: {e}")


def setup_logging(log_level: str = "INFO", initialize: bool = True) -> logging.Logger:
    """
    Convenience function to setup logging configuration
    
    Args:
        log_level: Logging level (DEBUG, INFO, WARNING, ERROR)
        initialize: Whether to initialize (create backup) log files
        
    Returns:
        Configured root logger
    """
    config = LoggingConfig()
    return config.setup_logging(log_level, initialize)


def get_logger(name: str) -> logging.Logger:
    """
    Get a logger instance for a specific module
    
    Args:
        name: Logger name (typically __name__)
        
    Returns:
        Logger instance
    """
    return logging.getLogger(f'morizo_ai.{name}')


# Environment-based log level
def get_log_level() -> str:
    """
    Get log level from environment variable with environment-based defaults
    
    Priority:
    1. LOG_LEVEL environment variable (if explicitly set)
    2. ENVIRONMENT-based default (if LOG_LEVEL not set)
    3. Default to INFO
    
    Environment defaults:
    - production: INFO (suppress DEBUG logs)
    - development: DEBUG (output all logs)
    - staging: WARNING (suppress INFO logs)
    """
    environment = os.getenv('ENVIRONMENT', 'development').lower()
    log_level = os.getenv('LOG_LEVEL', '').upper()
    
    # デバッグ用: 環境変数の値を確認（printで出力）
    print(f"🔍 [LOGGING] ENVIRONMENT={environment}, LOG_LEVEL={log_level if log_level else '(not set)'}")
    
    # 環境変数LOG_LEVELが明示的に設定されている場合はそれを使用
    if log_level:
        print(f"🔍 [LOGGING] Using explicit LOG_LEVEL: {log_level}")
        return log_level
    
    # 環境に基づくデフォルト値
    environment_defaults = {
        'production': 'INFO',
        'development': 'DEBUG',
        'staging': 'WARNING'
    }
    
    result = environment_defaults.get(environment, 'INFO')
    print(f"🔍 [LOGGING] Using ENVIRONMENT-based default: {environment} -> {result}")
    return result


if __name__ == "__main__":
    # Quick verification
    print("✅ ロギング設定が利用可能です")
