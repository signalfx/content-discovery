#!/usr/bin/env python3
"""
Validate that all changed content files have corresponding release notes entries

This script ensures that when content files are modified, they are documented
in the release notes. This prevents undocumented changes from being deployed.
"""

import os
import sys
import subprocess
import yaml
from pathlib import Path
from typing import Set, List, Dict, Any

# Content folders to track
CONTENT_FOLDERS = ['detector', 'navigators', 'group']

# Release notes file
RELEASE_NOTES_FILE = 'content_release_notes.yaml'


class ReleaseNotesValidator:
    """Validates that changed content files are documented in release notes"""
    
    def __init__(self):
        self.changed_files: Set[str] = set()
        self.documented_files: Set[str] = set()
        self.missing_files: Set[str] = set()
    
    def get_changed_content_files(self, target_branch: str = 'origin/master') -> Set[str]:
        """Get list of changed content files compared to target branch"""
        try:
            # Get the diff against target branch
            cmd = [
                'git', 'diff', '--name-only',
                target_branch, 'HEAD',
                '--',
                *[f'{folder}/' for folder in CONTENT_FOLDERS]
            ]
            
            result = subprocess.run(cmd, capture_output=True, text=True, check=True)
            
            if not result.stdout.strip():
                return set()
            
            # Filter only .json files
            changed_files = set()
            for line in result.stdout.strip().split('\n'):
                if line.endswith('.json'):
                    changed_files.add(line)
            
            return changed_files
            
        except subprocess.CalledProcessError as e:
            print(f'⚠ Could not get changed files: {e}')
            return set()
    
    def get_documented_files(self) -> Set[str]:
        """Get list of files documented in release notes"""
        if not Path(RELEASE_NOTES_FILE).exists():
            print(f'⚠ Release notes file not found: {RELEASE_NOTES_FILE}')
            return set()
        
        try:
            with open(RELEASE_NOTES_FILE, 'r', encoding='utf-8') as f:
                release_notes = yaml.safe_load(f)
            
            documented_files = set()
            
            # Traverse all versions and collect files_modified
            if 'versions' in release_notes:
                for version, version_data in release_notes['versions'].items():
                    if 'files' in version_data:
                        for file_entry in version_data['files']:
                            if 'files_modified' in file_entry:
                                for file_path in file_entry['files_modified']:
                                    documented_files.add(file_path)
            
            return documented_files
            
        except Exception as e:
            print(f'⚠ Could not parse release notes: {e}')
            return set()
    
    def validate(self, target_branch: str = 'origin/master') -> bool:
        """Validate that all changed files are documented"""
        
        print('🔍 Validating release notes coverage...\n')
        
        # Get changed files
        self.changed_files = self.get_changed_content_files(target_branch)
        
        if not self.changed_files:
            print('✓ No content files changed')
            return True
        
        print(f'📝 Found {len(self.changed_files)} changed content file(s):')
        for file in sorted(self.changed_files):
            print(f'  - {file}')
        
        # Get documented files
        self.documented_files = self.get_documented_files()
        
        print(f'\n📋 Found {len(self.documented_files)} file(s) in release notes')
        
        # Find missing files
        self.missing_files = self.changed_files - self.documented_files
        
        if self.missing_files:
            print(f'\n❌ VALIDATION FAILED: {len(self.missing_files)} changed file(s) not documented in release notes:')
            for file in sorted(self.missing_files):
                print(f'  ✗ {file}')
            
            print('\n💡 To fix this:')
            print(f'   1. Run: python scripts/generate_release_notes_from_master.py')
            print(f'   2. Commit the updated {RELEASE_NOTES_FILE} file')
            print('   3. Push your changes again')
            
            return False
        
        print(f'\n✅ VALIDATION PASSED: All changed files are documented in release notes')
        return True


def main():
    """Entry point"""
    
    # Get target branch from environment (for GitLab CI) or use default
    target_branch = os.getenv('CI_MERGE_REQUEST_TARGET_BRANCH_NAME', 'origin/master')
    
    # In CI, use the remote branch name format
    if os.getenv('CI'):
        target_branch = f'origin/{target_branch}' if not target_branch.startswith('origin/') else target_branch
    
    validator = ReleaseNotesValidator()
    
    try:
        is_valid = validator.validate(target_branch)
        
        if not is_valid:
            sys.exit(1)
        
        sys.exit(0)
        
    except Exception as e:
        print(f'\n❌ Fatal error during validation: {e}')
        import traceback
        traceback.print_exc()
        sys.exit(1)


if __name__ == '__main__':
    main()
