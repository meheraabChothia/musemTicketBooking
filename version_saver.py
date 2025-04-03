import os
import shutil
from datetime import datetime

def read_version():
    """Read the current version number from version.txt"""
    version_file = os.path.join('backups', 'version.txt')
    if not os.path.exists(version_file):
        return 0
    with open(version_file, 'r') as f:
        return int(f.read().strip())

def write_version(version):
    """Write the new version number to version.txt"""
    version_file = os.path.join('backups', 'version.txt')
    with open(version_file, 'w') as f:
        f.write(str(version))

def create_backup():
    # Files to backup
    files_to_backup = {
        'simple_chatbot/app.py': 'app.py',
        'simple_chatbot/templates/chat.html': 'chat.html',
        'simple_chatbot/templates/login.html': 'login.html'
    }
    
    # Create backups directory if it doesn't exist
    if not os.path.exists('backups'):
        os.makedirs('backups')
    
    # Get current version
    current_version = read_version()
    
    # Create new version directory
    backup_dir = os.path.join('backups', f'version_{current_version}')
    os.makedirs(backup_dir)
    
    # Copy files
    for source, dest in files_to_backup.items():
        if os.path.exists(source):
            shutil.copy2(source, os.path.join(backup_dir, dest))
        else:
            print(f"Warning: Source file {source} not found")
    
    # Add timestamp file
    timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    with open(os.path.join(backup_dir, 'backup_info.txt'), 'w') as f:
        f.write(f"Backup created at: {timestamp}\n")
        f.write(f"Version: {current_version}\n")
    
    # Increment version number
    write_version(current_version + 1)
    
    print(f"Backup completed: version_{current_version}")
    print(f"Files backed up to: {backup_dir}")

if __name__ == "__main__":
    create_backup() 