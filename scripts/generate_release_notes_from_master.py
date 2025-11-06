#!/usr/bin/env python3
"""
AI-Powered Release Notes Generator - Master Branch Commits

This script generates release notes from commits to master branch.
By default, analyzes only the last commit (most recent changes).
Use --commits N to analyze more commits.
"""

import os
import sys
import json
import subprocess
import time
import base64
import yaml
import argparse
from pathlib import Path
from datetime import datetime
from typing import List, Dict, Optional, Any
import requests

# Bridge IT API Configuration - Read from environment variables
BRIDGE_API_CLIENT_ID = os.getenv('BRIDGE_API_CLIENT_ID')
BRIDGE_API_CLIENT_SECRET = os.getenv('BRIDGE_API_CLIENT_SECRET')
BRIDGE_API_APP_KEY = os.getenv('BRIDGE_API_APP_KEY')
BRIDGE_API_HOSTNAME = 'chat-ai.cisco.com'
BRIDGE_API_MODEL_NAME = os.getenv('BRIDGE_API_MODEL_NAME', 'gpt-4.1')
BRIDGE_API_PATH = f'/openai/deployments/{BRIDGE_API_MODEL_NAME}/chat/completions'
BRIDGE_API_TEMPERATURE = float(os.getenv('BRIDGE_API_TEMPERATURE', '0.3'))
BRIDGE_API_TOP_P = float(os.getenv('BRIDGE_API_TOP_P', '0.25'))

AUTH_API_HOSTNAME = 'id.cisco.com'
AUTH_API_PATH = '/oauth2/default/v1/token'

# Content folders to analyze
CONTENT_FOLDERS = ['detector', 'navigators', 'group']

# Default number of commits to analyze (just the latest)
DEFAULT_NUM_COMMITS = 1

# Output file
OUTPUT_FILE = 'content_release_notes.yaml'


class ReleaseNotesGenerator:
    """Main class for generating release notes from master branch commits using AI"""
    
    def __init__(self, num_commits: int = DEFAULT_NUM_COMMITS):
        self.access_token: Optional[str] = None
        self.processed_count = 0
        self.skipped_count = 0
        self.error_count = 0
        self.num_commits = num_commits
        
    def authenticate(self) -> str:
        """Authenticate with Bridge IT API"""
        if not all([BRIDGE_API_CLIENT_ID, BRIDGE_API_CLIENT_SECRET, BRIDGE_API_APP_KEY]):
            print("✗ Error: Missing required environment variables")
            print("  Required: BRIDGE_API_CLIENT_ID, BRIDGE_API_CLIENT_SECRET, BRIDGE_API_APP_KEY")
            sys.exit(1)
        
        # Create basic auth token
        credentials = f"{BRIDGE_API_CLIENT_ID}:{BRIDGE_API_CLIENT_SECRET}"
        auth_token = base64.b64encode(credentials.encode()).decode()
        
        headers = {
            'Content-Type': 'application/x-www-form-urlencoded',
            'Authorization': f'Basic {auth_token}'
        }
        
        data = {'grant_type': 'client_credentials'}
        
        try:
            response = requests.post(
                f'https://{AUTH_API_HOSTNAME}{AUTH_API_PATH}',
                headers=headers,
                data=data,
                timeout=30
            )
            response.raise_for_status()
            
            token = response.json()['access_token']
            print('✓ Successfully authenticated with Bridge IT')
            return token
            
        except Exception as e:
            print(f'✗ Failed to authenticate with Bridge IT: {e}')
            sys.exit(1)
    
    def get_master_commits(self) -> List[Dict[str, Any]]:
        """Get last N commits from master branch"""
        try:
            # Get commits from master
            cmd = [
                'git', 'log', 'master',
                f'-{self.num_commits}',
                '--pretty=format:%H|%an|%ae|%ad|%s',
                '--date=iso',
                '--',
                *CONTENT_FOLDERS
            ]
            
            result = subprocess.run(cmd, capture_output=True, text=True, check=True)
            
            if not result.stdout.strip():
                return []
            
            commits = []
            for line in result.stdout.strip().split('\n'):
                if not line:
                    continue
                
                parts = line.split('|', 4)
                if len(parts) < 5:
                    continue
                
                commit_hash, author, email, date_str, message = parts
                
                commits.append({
                    'commit_hash': commit_hash,
                    'author': author,
                    'email': email,
                    'date': date_str.split()[0],  # Extract YYYY-MM-DD
                    'message': message.strip()
                })
            
            return commits
            
        except subprocess.CalledProcessError as e:
            print(f'⚠ Failed to get git commits: {e}')
            return []
    
    def get_commit_changes(self, commit_hash: str) -> List[Dict[str, str]]:
        """Get files changed in a specific commit"""
        try:
            # Get list of changed files in content folders
            cmd = [
                'git', 'diff-tree', '--no-commit-id', '--name-only', '-r',
                commit_hash, '--',
                *CONTENT_FOLDERS
            ]
            
            result = subprocess.run(cmd, capture_output=True, text=True, check=True)
            
            if not result.stdout.strip():
                return []
            
            files = []
            for file_path in result.stdout.strip().split('\n'):
                if not file_path or not file_path.endswith('.json'):
                    continue
                
                # Determine content type
                if file_path.startswith('detector/'):
                    content_type = 'detector'
                elif file_path.startswith('navigators/'):
                    content_type = 'navigator'
                elif file_path.startswith('group/'):
                    content_type = 'dashboard_group'
                else:
                    continue
                
                # Get content name from file
                content_name = self.get_content_name(file_path)
                
                # Get diff for this file
                diff = self.get_file_diff(commit_hash, file_path)
                
                files.append({
                    'path': file_path,
                    'name': content_name,
                    'category': content_type,
                    'diff': diff
                })
            
            return files
            
        except subprocess.CalledProcessError as e:
            print(f'⚠ Failed to get commit changes: {e}')
            return []
    
    def get_file_diff(self, commit_hash: str, file_path: str) -> str:
        """Get diff for a specific file in a commit"""
        try:
            cmd = ['git', 'show', f'{commit_hash}:{file_path}']
            result = subprocess.run(cmd, capture_output=True, text=True, check=True)
            return result.stdout[:2000]  # Limit diff size
        except:
            return ""
    
    def get_content_name(self, file_path: str) -> str:
        """Extract content name from file"""
        try:
            # Try to read the file at current HEAD
            cmd = ['git', 'show', f'HEAD:{file_path}']
            result = subprocess.run(cmd, capture_output=True, text=True)
            
            if result.returncode == 0:
                content = json.loads(result.stdout)
                return content.get('name', Path(file_path).stem)
        except:
            pass
        
        return Path(file_path).stem
    
    def generate_version_from_commit(self, commit: Dict[str, Any], files: List[Dict[str, str]], existing_versions: List[str]) -> Dict[str, Any]:
        """Generate a release notes version entry from a commit using AI"""
        
        # Generate semantic version number based on existing versions
        version = self.get_next_version(commit, existing_versions)
        
        system_prompt = """You are a technical analyst creating release notes from git commits.
Analyze the commit and generate a version number using semantic versioning.

Output ONLY valid JSON - no markdown, no explanations, no code blocks.

Return a JSON object with:
- version_bump: one of (major|minor|patch) - suggest version increment based on change significance

Use semantic versioning guidelines:
- MAJOR: Breaking changes, major feature rewrites
- MINOR: New features, non-breaking enhancements
- PATCH: Bug fixes, small tweaks

Note: Change details will be captured at the file level, so you only need to provide the version bump."""

        # Format file changes
        file_summaries = []
        for idx, file in enumerate(files, 1):
            file_summaries.append(f"""
--- FILE {idx}: {file['name']} ({file['category']}) ---
Path: {file['path']}
Diff preview:
{file['diff'][:500]}
---""")
        
        user_prompt = f"""Analyze these changes and generate a public-facing release notes entry.

CHANGE SUMMARY:
{commit['message']}
Date: {commit['date']}

FILES CHANGED ({len(files)} files):
{''.join(file_summaries)}

Return a JSON object with the version bump:
{{
  "version_bump": "patch"
}}

Guidelines:
- Breaking changes → version_bump="major"
- New features → version_bump="minor"  
- Bug fixes, minor updates → version_bump="patch"

Determine the version bump now:"""

        payload = {
            "messages": [
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": user_prompt}
            ],
            "user": json.dumps({"appkey": BRIDGE_API_APP_KEY}),
            "temperature": BRIDGE_API_TEMPERATURE,
            "top_p": BRIDGE_API_TOP_P,
            "max_tokens": 500
        }
        
        headers = {
            "api-key": self.access_token,
            "Content-Type": "application/json"
        }
        
        try:
            response = requests.post(
                f'https://{BRIDGE_API_HOSTNAME}{BRIDGE_API_PATH}',
                headers=headers,
                json=payload,
                timeout=60
            )
            response.raise_for_status()
            
            ai_response = response.json()['choices'][0]['message']['content']
            
            # Extract JSON from response
            json_str = ai_response.strip()
            if json_str.startswith('```'):
                json_str = json_str.replace('```json\n', '').replace('```json', '')
                json_str = json_str.replace('\n```', '').replace('```', '')
            
            changelog_data = json.loads(json_str)
            
            # Build version entry (no commit details for public docs)
            # Note: description, change_type and breaking_change are all at file level only
            version_entry = {
                'date': commit['date'],
                'files': []
            }
            
            # Generate file-level descriptions with AI
            for file in files:
                file_details = self.generate_file_details(file, commit)
                version_entry['files'].append({
                    'name': file['name'],
                    'category': file['category'],
                    'description': file_details['description'],
                    'change_type': file_details['change_type'],
                    'breaking_change': file_details['breaking_change'],
                    'files_modified': [file['path']]
                })
            
            return version, version_entry
            
        except Exception as e:
            print(f'  ✗ Failed to generate release notes with AI: {e}')
            # Fallback: create basic entry without AI
            version_entry = {
                'date': commit['date'],
                'files': [{
                    'name': f['name'], 
                    'category': f['category'], 
                    'description': commit['message'],
                    'change_type': 'updated',
                    'breaking_change': False,
                    'files_modified': [f['path']]
                } for f in files]
            }
            return version, version_entry
    
    def generate_file_details(self, file: Dict[str, str], commit: Dict[str, Any]) -> Dict[str, Any]:
        """Generate detailed change information for a specific file using AI"""
        
        system_prompt = """You are a technical analyst creating file-level change documentation.
Analyze the changes and provide structured metadata.

Output ONLY valid JSON - no markdown, no explanations, no code blocks.

Return a JSON object with:
- description: One concise sentence (max 15 words) about what changed
- change_type: one of (created|updated|metric_changed|visualization_changed|metadata_changed|detector_rule_changed|deprecated|deleted|migrated|bug_fix|performance_improvement)
- breaking_change: boolean (true if this file's changes break compatibility)"""
        
        user_prompt = f"""Analyze the changes to this file:

FILE: {file['name']} ({file['category']})
COMMIT: {commit['message']}

CHANGES:
{file['diff'][:800]}

Return a JSON object describing this file's changes:
{{
  "description": "Brief description of what changed in this file",
  "change_type": "updated",
  "breaking_change": false
}}

Generate the file details now:"""

        payload = {
            "messages": [
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": user_prompt}
            ],
            "user": json.dumps({"appkey": BRIDGE_API_APP_KEY}),
            "temperature": 0.3,
            "top_p": 0.25,
            "max_tokens": 150
        }
        
        headers = {
            "api-key": self.access_token,
            "Content-Type": "application/json"
        }
        
        try:
            response = requests.post(
                f'https://{BRIDGE_API_HOSTNAME}{BRIDGE_API_PATH}',
                headers=headers,
                json=payload,
                timeout=30
            )
            response.raise_for_status()
            
            ai_response = response.json()['choices'][0]['message']['content']
            
            # Extract JSON from response
            json_str = ai_response.strip()
            if json_str.startswith('```'):
                json_str = json_str.replace('```json\n', '').replace('```json', '')
                json_str = json_str.replace('\n```', '').replace('```', '')
            
            file_details = json.loads(json_str)
            
            return {
                'description': file_details.get('description', f"Updated {file['name']}"),
                'change_type': file_details.get('change_type', 'updated'),
                'breaking_change': file_details.get('breaking_change', False)
            }
            
        except Exception as e:
            # Fallback to generic details
            return {
                'description': f"Updated {file['name']}",
                'change_type': 'updated',
                'breaking_change': False
            }
    
    def get_next_version(self, commit: Dict[str, Any], existing_versions: List[str]) -> str:
        """Generate semantic version number based on existing versions"""
        
        if not existing_versions:
            # First version
            return "1.0.0"
        
        # Parse the latest version
        latest = existing_versions[0]
        try:
            parts = latest.split('.')
            major, minor, patch = int(parts[0]), int(parts[1]), int(parts[2])
        except:
            # If parsing fails, start from 1.0.0
            return "1.0.0"
        
        # For now, increment patch version
        # In future, AI can suggest major/minor/patch based on change analysis
        patch += 1
        
        return f"{major}.{minor}.{patch}"
    
    def load_existing_release_notes(self) -> Dict[str, Any]:
        """Load existing release notes file"""
        if Path(OUTPUT_FILE).exists():
            try:
                with open(OUTPUT_FILE, 'r', encoding='utf-8') as f:
                    return yaml.safe_load(f) or self.get_default_structure()
            except Exception as e:
                                print(f'⚠ Could not parse existing release notes: {e}')
            return self.get_default_release_notes_structure()
    
    def get_default_release_notes_structure(self) -> Dict[str, Any]:
        """Get default release notes structure"""
        
        return self.get_default_structure()
    
    def get_default_structure(self) -> Dict[str, Any]:
        """Get default changelog structure"""
        return {
            'metadata': {
                'version': '2.0.0',
                'last_updated': datetime.utcnow().isoformat() + 'Z',
                'description': 'Version-based release notes tracking system',
                'structure': 'Grouped by version number with files changed in each version'
            },
            'versions': {},
            'change_types': {
                'created': 'Initial creation of content piece',
                'updated': 'General update to existing content',
                'metric_changed': 'Changes to metric queries or calculations',
                'visualization_changed': 'Changes to charts, dashboards, or display',
                'metadata_changed': 'Changes to metadata (tags, descriptions, etc.)',
                'detector_rule_changed': 'Changes to detector rules or conditions',
                'deprecated': 'Content marked as deprecated',
                'deleted': 'Content removed from system',
                'migrated': 'Content migrated from Smart Agent to OTel or other source',
                'bug_fix': 'Bug fix or correction',
                'performance_improvement': 'Performance optimization'
            },
            'categories': {
                'detector': 'Detector/Alert configuration',
                'navigator': 'Navigator configuration',
                'dashboard_group': 'Dashboard group configuration'
            }
        }
    
    def save_release_notes(self, release_notes: Dict[str, Any]):
        """Save release notes to YAML file"""
        # Update last_updated timestamp
        if 'metadata' in release_notes:
            release_notes['metadata']['last_updated'] = datetime.utcnow().isoformat() + 'Z'
        
        # Sort versions in descending order
        if 'versions' in release_notes:
            sorted_versions = dict(sorted(release_notes['versions'].items(), key=lambda x: x[0], reverse=True))
            release_notes['versions'] = sorted_versions
        
        with open(OUTPUT_FILE, 'w') as f:
            yaml.dump(release_notes, f, default_flow_style=False, allow_unicode=True, sort_keys=False, width=120)
        print(f'✓ Release notes saved to {OUTPUT_FILE}')
    
    def run(self):
        """Main execution function"""
        print('🚀 Starting release notes generation from master branch commits...\n')
        
        # Authenticate
        self.access_token = self.authenticate()
        
        # Get commits from master
        commit_msg = f"last {self.num_commits} commit(s)" if self.num_commits > 1 else "last commit"
        print(f'\n📁 Fetching {commit_msg} from master...')
        commits = self.get_master_commits()
        print(f'✓ Found {len(commits)} commits with content changes\n')
        
        if not commits:
            print('⚠ No commits found!')
            return
        
        # Load existing release notes
        release_notes = self.load_existing_release_notes()
        
        # Process each commit
        for idx, commit in enumerate(commits, 1):
            commit_short = commit['commit_hash'][:7]
            print(f"\n[{idx}/{len(commits)}] Processing commit {commit_short}: {commit['message'][:60]}...")
            
            # Get files changed in this commit
            files = self.get_commit_changes(commit['commit_hash'])
            
            if not files:
                print('  ⊘ No content files changed, skipping')
                self.skipped_count += 1
                continue
            
            print(f"  ✓ Found {len(files)} content files changed")
            
            # Generate release notes entry with AI
            print('  🤖 Generating release notes with AI...')
            try:
                # Get existing version list
                existing_versions = sorted(release_notes['versions'].keys(), reverse=True)
                
                version, version_entry = self.generate_version_from_commit(commit, files, existing_versions)
                
                # Add to release notes
                release_notes['versions'][version] = version_entry
                
                print(f"  ✓ Created version entry: {version}")
                self.processed_count += 1
                
            except Exception as e:
                print(f"  ✗ Error: {e}")
                self.error_count += 1
                continue
            
            # Add a small delay to avoid rate limiting
            time.sleep(0.5)
        
        # Save the release notes
        print('\n💾 Saving release notes...')
        self.save_release_notes(release_notes)
        
        # Summary
        self.print_summary(len(commits))
    
    def print_summary(self, total_commits: int):
        """Print execution summary"""
        print('\n' + '=' * 60)
        print('📊 SUMMARY')
        print('=' * 60)
        print(f'✓ Processed: {self.processed_count} commits')
        print(f'⊘ Skipped:   {self.skipped_count} commits (no content changes)')
        print(f'✗ Errors:    {self.error_count} commits')
        print(f'📄 Total:     {total_commits} commits')
        print('=' * 60)


def main():
    """Entry point"""
    parser = argparse.ArgumentParser(
        description='Generate release notes from master branch commits',
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  # Generate release notes for the last commit only (default)
  %(prog)s

  # Generate release notes for the last 10 commits
  %(prog)s --commits 10

  # Regenerate all release notes from last 50 commits
  %(prog)s --commits 50

  # Load environment from file
  export $(cat scripts/env.env | xargs) && %(prog)s
        """
    )
    
    parser.add_argument(
        '-n', '--commits',
        type=int,
        default=DEFAULT_NUM_COMMITS,
        metavar='N',
        help=f'Number of commits to analyze from master branch (default: {DEFAULT_NUM_COMMITS})'
    )
    
    parser.add_argument(
        '--regenerate',
        action='store_true',
        help='Regenerate all release notes from last 50 commits (same as --commits 50)'
    )
    
    args = parser.parse_args()
    
    # Handle --regenerate flag
    num_commits = 50 if args.regenerate else args.commits
    
    try:
        generator = ReleaseNotesGenerator(num_commits=num_commits)
        generator.run()
    except KeyboardInterrupt:
        print('\n\n⚠ Interrupted by user')
        sys.exit(1)
    except Exception as e:
        print(f'\n❌ Fatal error: {e}')
        import traceback
        traceback.print_exc()
        sys.exit(1)


if __name__ == '__main__':
    main()
