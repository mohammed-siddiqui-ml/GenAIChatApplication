"""
Folder Watcher Service for Automatic Document Ingestion

Monitors a local folder for new PDF and video files, automatically
uploading and processing them for the RAG system.

For internal testing/stage environment only.
"""

import os
import logging
import time
from pathlib import Path
from typing import Optional
from watchdog.observers import Observer
from watchdog.events import FileSystemEventHandler, FileCreatedEvent

logger = logging.getLogger(__name__)


class DocumentWatchHandler(FileSystemEventHandler):
    """Handle file system events for document folder"""
    
    SUPPORTED_EXTENSIONS = {
        # PDFs
        '.pdf': 'pdf',
        # Videos
        '.mp4': 'video',
        '.avi': 'video',
        '.mov': 'video',
        '.mkv': 'video',
        '.webm': 'video',
        '.flv': 'video',
        '.m4v': 'video',
    }
    
    def __init__(self, data_source_id: int):
        """
        Initialize handler
        
        Args:
            data_source_id: ID of the "Local Folder" data source in database
        """
        self.data_source_id = data_source_id
        super().__init__()
    
    def on_created(self, event: FileCreatedEvent):
        """Handle new file creation"""
        if event.is_directory:
            return
        
        filepath = event.src_path
        ext = Path(filepath).suffix.lower()
        
        if ext in self.SUPPORTED_EXTENSIONS:
            file_type = self.SUPPORTED_EXTENSIONS[ext]
            logger.info(f"🆕 New {file_type} detected: {filepath}")
            
            # Wait for file to be fully written (important for large files)
            self._wait_for_file_ready(filepath)
            
            # Dispatch Celery task for processing
            try:
                from tasks.ingestion.folder_watch import process_file_from_folder
                task = process_file_from_folder.delay(
                    data_source_id=self.data_source_id,
                    filepath=filepath,
                    file_type=file_type
                )
                logger.info(f"📋 Dispatched task {task.id} for {filepath}")
            except Exception as e:
                logger.error(f"Failed to dispatch task for {filepath}: {e}")
    
    def _wait_for_file_ready(self, filepath: str, max_wait: int = 30):
        """
        Wait for file to be fully written
        
        Args:
            filepath: Path to file
            max_wait: Maximum seconds to wait
        """
        prev_size = -1
        wait_time = 0
        
        while wait_time < max_wait:
            try:
                current_size = os.path.getsize(filepath)
                if current_size == prev_size and current_size > 0:
                    logger.debug(f"File ready: {filepath} ({current_size} bytes)")
                    return True
                prev_size = current_size
                time.sleep(1)
                wait_time += 1
            except OSError:
                time.sleep(1)
                wait_time += 1
        
        logger.warning(f"File may not be fully written: {filepath}")
        return True


class FolderWatcherService:
    """Service to monitor folder and manage observer"""
    
    def __init__(self, watch_path: str, data_source_id: int):
        """
        Initialize folder watcher
        
        Args:
            watch_path: Path to folder to watch
            data_source_id: Database ID of the data source
        """
        self.watch_path = watch_path
        self.data_source_id = data_source_id
        self.observer: Optional[Observer] = None
        
        # Create watch folder if it doesn't exist
        Path(watch_path).mkdir(parents=True, exist_ok=True)
        logger.info(f"📁 Watch folder initialized: {watch_path}")
    
    def start(self):
        """Start watching folder"""
        if self.observer and self.observer.is_alive():
            logger.warning("Folder watcher already running")
            return
        
        event_handler = DocumentWatchHandler(self.data_source_id)
        self.observer = Observer()
        self.observer.schedule(event_handler, self.watch_path, recursive=False)
        self.observer.start()
        
        logger.info(f"📁 Started watching folder: {self.watch_path}")
        logger.info(f"   Supported formats: PDF, MP4, AVI, MOV, MKV, WEBM, FLV, M4V")
    
    def stop(self):
        """Stop watching folder"""
        if self.observer:
            self.observer.stop()
            self.observer.join()
            logger.info("🛑 Stopped folder watcher")
    
    def is_running(self) -> bool:
        """Check if watcher is running"""
        return self.observer is not None and self.observer.is_alive()
