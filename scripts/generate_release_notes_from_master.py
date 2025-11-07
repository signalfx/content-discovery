#!/usr/bin/env python3
"""
AI-Powered Changelog Generator - Master Branch Commits

This script generates changelog from commits to master branch.
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
DEFAULT_NUM_COMMITS = 50

# Output files
OUTPUT_YAML = 'content_changelog.yaml'
OUTPUT_MARKDOWN = 'CHANGELOG.md'


class ChangelogGenerator:
    """Main class for generating changelog from master branch commits using AI"""
    
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
    
    def generate_version_from_commit(self, commit: Dict[str, Any], files: List[Dict[str, str]], existing_changelog: Dict[str, Any]) -> Dict[str, Any]:
        """Generate a changelog version entry from a commit using AI"""
        
        # Generate date-based version key (for uniqueness and sorting)
        version_key = self.get_next_version(commit['date'], existing_changelog.get('versions', {}))
        
        # Temporary version number (will be reassigned later in chronological order)
        user_version = "1.0.0"
        
        # Build version entry
        version_entry = {
            'version': user_version,
            'date': commit['date'],
            'files': []
        }
        
        # Generate file-level descriptions with AI
        try:
            for file in files:
                file_details = self.generate_file_details(file, commit)
                version_entry['files'].append({
                    'name': file['name'],
                    'category': file['category'],
                    'description': file_details['description'],
                    'change_type': file_details['change_type'],
                    'breaking_change': file_details['breaking_change']
                })
            
            return version_key, version_entry
            
        except Exception as e:
            print(f'  ✗ Failed to generate release notes with AI: {e}')
            # Fallback: create basic entry without AI
            version_entry['files'] = [{
                'name': f['name'], 
                'category': f['category'], 
                'description': commit['message'],
                'change_type': 'updated',
                'breaking_change': False
            } for f in files]
            return version_key, version_entry
    
    def generate_file_details(self, file: Dict[str, str], commit: Dict[str, Any]) -> Dict[str, Any]:
        """Generate detailed change information for a specific file using AI"""
        
        system_prompt = """You are a technical analyst creating file-level change documentation.
Analyze the changes and provide structured metadata.

Output ONLY valid JSON - no markdown, no explanations, no code blocks.

Return JSON with:
- description: One concise sentence (max 15 words) about what changed
- change_type: one of (created|updated|bug_fix|deleted)
- breaking_change: boolean (true if breaks compatibility)"""
        
        user_prompt = f"""Analyze changes to: {file['name']} ({file['category']})

COMMIT: {commit['message']}
CHANGES: {file['diff'][:800]}

Return JSON:
{{
  "description": "Brief description",
  "change_type": "updated",
  "breaking_change": false
}}"""

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
            
            response_data = response.json()
            if not response_data or 'choices' not in response_data or not response_data['choices']:
                raise Exception("Invalid API response")
            
            ai_response = response_data['choices'][0]['message']['content']
            
            # Extract JSON from response
            json_str = ai_response.strip()
            if json_str.startswith('```'):
                json_str = json_str.replace('```json\n', '').replace('```json', '').replace('\n```', '').replace('```', '')
            
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
    
    def get_next_version(self, commit_date: str, existing_versions: Dict[str, Any]) -> str:
        """Generate date-based version number (YYYY.MM.DD.N)"""
        
        # Parse date from commit (YYYY-MM-DD)
        date_parts = commit_date.split('-')
        year, month, day = date_parts[0], date_parts[1], date_parts[2]
        
        # Find existing versions for this date
        date_prefix = f"{year}.{month}.{day}"
        same_date_versions = [
            v for v in existing_versions.keys() 
            if v.startswith(date_prefix)
        ]
        
        if not same_date_versions:
            # First version for this date
            return f"{date_prefix}.1"
        
        # Find max sequence number for this date
        max_seq = 0
        for v in same_date_versions:
            try:
                seq = int(v.split('.')[-1])
                max_seq = max(max_seq, seq)
            except:
                pass
        
        return f"{date_prefix}.{max_seq + 1}"
    
    def get_next_user_version(self, existing_versions: Dict[str, Any]) -> int:
        """Generate simple incrementing version number (user-facing)"""
        
        if not existing_versions:
            return 1
        
        # Find max user version from all existing entries
        max_version = 0
        for entry in existing_versions.values():
            if 'version' in entry:
                try:
                    max_version = max(max_version, int(entry['version']))
                except:
                    pass
        
        return max_version + 1
    
    def reassign_user_versions(self, changelog: Dict[str, Any]):
        """Reassign user version numbers in semantic versioning format (major.minor.patch)"""
        versions = changelog.get('versions', {})
        
        if not versions:
            return
        
        # Parse and sort by date-based version key (YYYY.MM.DD.N) ascending (oldest first)
        def parse_version(v):
            try:
                return tuple(int(p) for p in v.split('.'))
            except:
                return (0, 0, 0, 0)
        
        sorted_keys = sorted(versions.keys(), key=parse_version, reverse=False)
        
        # Assign semantic version numbers: 1.0.0 (oldest) to 1.N.0 (newest)
        for idx, version_key in enumerate(sorted_keys, 1):
            versions[version_key]['version'] = f"1.{idx}.0"
    
    def load_existing_changelog(self) -> Dict[str, Any]:
        """Load existing changelog file"""
        if Path(OUTPUT_YAML).exists():
            try:
                with open(OUTPUT_YAML, 'r', encoding='utf-8') as f:
                    return yaml.safe_load(f) or self.get_default_structure()
            except Exception as e:
                print(f'⚠ Could not parse existing changelog: {e}')
        return self.get_default_structure()
    
    def get_default_structure(self) -> Dict[str, Any]:
        """Get default changelog structure"""
        return {
            'metadata': {
                'version': '2.0.0',
                'last_updated': datetime.utcnow().isoformat() + 'Z',
                'description': 'Changelog tracking system for content changes',
                'structure': 'Grouped by version number with files changed in each version'
            },
            'versions': {},
            'change_types': {
                'created': 'Initial creation of content piece',
                'updated': 'General update to existing content',
                'bug_fix': 'Bug fix or correction',
                'deleted': 'Content removed from system'
            },
            'categories': {
                'detector': 'Detector/Alert configuration',
                'navigator': 'Navigator configuration',
                'dashboard_group': 'Dashboard group configuration'
            }
        }
    
    def save_changelog(self, changelog: Dict[str, Any]):
        """Save changelog to YAML and Markdown files"""
        # Update last_updated timestamp
        if 'metadata' in changelog:
            changelog['metadata']['last_updated'] = datetime.utcnow().isoformat() + 'Z'
        
        # Sort versions by version key (which is date-based YYYY.MM.DD.N) descending
        if 'versions' in changelog:
            def parse_version(v):
                """Parse date-based version YYYY.MM.DD.N into tuple"""
                try:
                    return tuple(int(p) for p in v.split('.'))
                except:
                    return (0, 0, 0, 0)
            
            sorted_versions = dict(sorted(
                changelog['versions'].items(), 
                key=lambda x: parse_version(x[0]), 
                reverse=True
            ))
            changelog['versions'] = sorted_versions
        
        # Save YAML
        with open(OUTPUT_YAML, 'w') as f:
            yaml.dump(changelog, f, default_flow_style=False, allow_unicode=True, sort_keys=False, width=120)
        print(f'✓ Changelog saved to {OUTPUT_YAML}')
        
        # Save Markdown
        self.save_markdown(changelog)
        print(f'✓ Changelog saved to {OUTPUT_MARKDOWN}')
    
    def save_markdown(self, changelog: Dict[str, Any]):
        """Generate and save markdown version of changelog"""
        lines = [
            '# Changelog',
            '',
            'All notable changes to this content will be documented in this file.',
            '',
            f'Last Updated: {changelog["metadata"]["last_updated"]}',
            '',
            '---',
            ''
        ]
        
        for version_key, version_data in changelog.get('versions', {}).items():
            date = version_data.get('date', '')
            user_version = version_data.get('version', version_key)
            lines.append(f'## [v{user_version}] - {date}')
            lines.append('')
            
            for file_entry in version_data.get('files', []):
                change_type = file_entry.get('change_type', 'updated').upper()
                name = file_entry.get('name', '')
                category = file_entry.get('category', '').replace('_', ' ').title()
                description = file_entry.get('description', '')
                breaking = ' **⚠️ BREAKING**' if file_entry.get('breaking_change') else ''
                
                lines.append(f'### {change_type}: {name} ({category}){breaking}')
                lines.append(f'{description}')
                lines.append('')
            
            lines.append('---')
            lines.append('')
        
        with open(OUTPUT_MARKDOWN, 'w', encoding='utf-8') as f:
            f.write('\n'.join(lines))
    
    def run(self):
        """Main execution function"""
        print('🚀 Starting changelog generation...\n')
        
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
        
        # Load existing changelog
        changelog = self.load_existing_changelog()
        
        # Process each commit
        for idx, commit in enumerate(commits, 1):
            commit_short = commit['commit_hash'][:7]
            print(f"\n[{idx}/{len(commits)}] {commit_short}: {commit['message'][:60]}...")
            
            # Get files changed in this commit
            files = self.get_commit_changes(commit['commit_hash'])
            
            if not files:
                print('  ⊘ No content files changed, skipping')
                self.skipped_count += 1
                continue
            
            print(f"  ✓ Found {len(files)} content files changed")
            print('  🤖 Generating changelog with AI...')
            
            try:
                # Generate version entry with date-based version number
                version, version_entry = self.generate_version_from_commit(commit, files, changelog)
                
                # Add to changelog
                changelog['versions'][version] = version_entry
                
                print(f"  ✓ Created version entry: {version}")
                self.processed_count += 1
                
            except Exception as e:
                print(f"  ✗ Error: {e}")
                self.error_count += 1
                continue
            
            # Small delay to avoid rate limiting
            time.sleep(0.5)
        
        # Re-assign user version numbers in chronological order (newest = highest)
        print('\n🔢 Assigning version numbers in chronological order...')
        self.reassign_user_versions(changelog)
        
        # Save the changelog
        print('\n💾 Saving changelog...')
        self.save_changelog(changelog)
        
        # Summary
        print('\n' + '=' * 60)
        print(f'✓ Processed: {self.processed_count} | ⊘ Skipped: {self.skipped_count} | ✗ Errors: {self.error_count}')
        print('=' * 60)


def main():
    """Entry point"""
    parser = argparse.ArgumentParser(
        description='Generate changelog from master branch commits',
        epilog='Examples:\n'
               '  %(prog)s                  # Last commit (default)\n'
               '  %(prog)s --commits 10     # Last 10 commits\n'
               '  %(prog)s --regenerate     # Last 50 commits',
        formatter_class=argparse.RawDescriptionHelpFormatter
    )
    
    parser.add_argument('-n', '--commits', type=int, default=DEFAULT_NUM_COMMITS,
                        help=f'Number of commits to analyze (default: {DEFAULT_NUM_COMMITS})')
    parser.add_argument('--regenerate', action='store_true',
                        help='Regenerate from last 50 commits')
    
    args = parser.parse_args()
    num_commits = 50 if args.regenerate else args.commits
    
    try:
        generator = ChangelogGenerator(num_commits=num_commits)
        generator.run()
    except KeyboardInterrupt:
        print('\n\n⚠ Interrupted by user')
        sys.exit(1)
    except Exception as e:
        print(f'\n❌ Fatal error: {e}')
        sys.exit(1)


if __name__ == '__main__':
    main()
