#!/usr/bin/env python3
"""
AI-Powered Changelog Generator - Feature Branch

This script generates changelog entries for changes in the current feature branch
compared to master. Designed to run as a pre-merge hook or in CI/CD pipeline.

Usage:
  python generate_changelog_for_branch.py              # Analyze current branch vs master
  python generate_changelog_for_branch.py --branch <name>  # Analyze specific branch
"""

import os
import sys
import json
import subprocess
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

AUTH_API_HOSTNAME = 'id.cisco.com'
AUTH_API_PATH = '/oauth2/default/v1/token'

# Content folders to analyze
CONTENT_FOLDERS = ['detector', 'navigators', 'group']

# Output files
OUTPUT_YAML = 'content_changelog.yaml'
OUTPUT_MARKDOWN = 'CHANGELOG.md'


class BranchChangelogGenerator:
    """Generate changelog entries for feature branch changes"""
    
    def __init__(self, branch_name: Optional[str] = None):
        self.access_token: Optional[str] = None
        self.branch_name = branch_name or self.get_current_branch()
        self.base_branch = 'master'
        
    def get_current_branch(self) -> str:
        """Get the current git branch name"""
        try:
            result = subprocess.run(
                ['git', 'rev-parse', '--abbrev-ref', 'HEAD'],
                capture_output=True, text=True, check=True
            )
            return result.stdout.strip()
        except subprocess.CalledProcessError:
            print("✗ Error: Could not determine current branch")
            sys.exit(1)
    
    def authenticate(self) -> str:
        """Authenticate with Bridge IT API"""
        if not all([BRIDGE_API_CLIENT_ID, BRIDGE_API_CLIENT_SECRET, BRIDGE_API_APP_KEY]):
            print("✗ Error: Missing required environment variables")
            print("  Required: BRIDGE_API_CLIENT_ID, BRIDGE_API_CLIENT_SECRET, BRIDGE_API_APP_KEY")
            sys.exit(1)
        
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
    
    def get_branch_changes(self) -> List[Dict[str, str]]:
        """Get files changed in current branch compared to master"""
        try:
            # Get list of changed files between this branch and master
            cmd = [
                'git', 'diff', '--name-only',
                f'{self.base_branch}...{self.branch_name}',
                '--',
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
                
                # Check if file is new, modified, or deleted
                change_status = self.get_file_status(file_path)
                
                # Get content name from file
                content_name = self.get_content_name(file_path)
                
                # Get diff for this file
                diff = self.get_file_diff(file_path)
                
                files.append({
                    'path': file_path,
                    'name': content_name,
                    'category': content_type,
                    'status': change_status,
                    'diff': diff
                })
            
            return files
            
        except subprocess.CalledProcessError as e:
            print(f'⚠ Failed to get branch changes: {e}')
            return []
    
    def get_file_status(self, file_path: str) -> str:
        """Determine if file is added, modified, or deleted"""
        try:
            # Check if file exists in master
            cmd = ['git', 'cat-file', '-e', f'{self.base_branch}:{file_path}']
            result_master = subprocess.run(cmd, capture_output=True)
            exists_in_master = result_master.returncode == 0
            
            # Check if file exists in current branch
            cmd = ['git', 'cat-file', '-e', f'{self.branch_name}:{file_path}']
            result_branch = subprocess.run(cmd, capture_output=True)
            exists_in_branch = result_branch.returncode == 0
            
            if not exists_in_master and exists_in_branch:
                return 'created'
            elif exists_in_master and not exists_in_branch:
                return 'deleted'
            else:
                return 'updated'
                
        except:
            return 'updated'
    
    def get_file_diff(self, file_path: str) -> str:
        """Get diff for a specific file"""
        try:
            cmd = ['git', 'diff', f'{self.base_branch}...{self.branch_name}', '--', file_path]
            result = subprocess.run(cmd, capture_output=True, text=True, check=True)
            return result.stdout[:2000]  # Limit diff size
        except:
            return ""
    
    def get_content_name(self, file_path: str) -> str:
        """Extract content name from file"""
        try:
            # Try to read the file from current branch
            cmd = ['git', 'show', f'{self.branch_name}:{file_path}']
            result = subprocess.run(cmd, capture_output=True, text=True)
            
            if result.returncode == 0:
                content = json.loads(result.stdout)
                return content.get('name', Path(file_path).stem)
        except:
            pass
        
        return Path(file_path).stem
    
    def get_branch_commit_messages(self) -> List[str]:
        """Get commit messages from this branch"""
        try:
            cmd = [
                'git', 'log', '--pretty=format:%s',
                f'{self.base_branch}..{self.branch_name}'
            ]
            result = subprocess.run(cmd, capture_output=True, text=True, check=True)
            return [msg.strip() for msg in result.stdout.strip().split('\n') if msg.strip()]
        except:
            return []
    
    def generate_file_details(self, file: Dict[str, str], commit_context: str) -> Dict[str, Any]:
        """Generate detailed change information for a specific file using AI"""
        
        system_prompt = """You are a technical analyst creating file-level change documentation.
Analyze the changes and provide structured metadata.

Output ONLY valid JSON - no markdown, no explanations, no code blocks.

Return JSON with:
- description: One concise sentence (max 15 words) about what changed
- change_type: one of (created|updated|bug_fix|deleted)
- breaking_change: boolean (true if breaks compatibility)"""
        
        user_prompt = f"""Analyze changes to: {file['name']} ({file['category']})

FILE STATUS: {file['status']}
BRANCH COMMITS: {commit_context}
CHANGES: {file['diff'][:800]}

Return JSON:
{{
  "description": "Brief description",
  "change_type": "{file['status']}",
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
            
            # Override change_type with file status if it's created or deleted
            change_type = file_details.get('change_type', file['status'])
            if file['status'] == 'created':
                change_type = 'created'
            elif file['status'] == 'deleted':
                change_type = 'deleted'
            
            return {
                'description': file_details.get('description', f"{file['status'].title()} {file['name']}"),
                'change_type': change_type,
                'breaking_change': file_details.get('breaking_change', False)
            }
            
        except Exception as e:
            # Fallback to basic details
            return {
                'description': f"{file['status'].title()} {file['name']}",
                'change_type': file['status'],
                'breaking_change': False
            }
    
    def get_next_version(self, commit_date: str, existing_versions: Dict[str, Any]) -> str:
        """Generate date-based version number (YYYY.MM.DD.N)"""
        date_parts = commit_date.split('-')
        year, month, day = date_parts[0], date_parts[1], date_parts[2]
        
        date_prefix = f"{year}.{month}.{day}"
        same_date_versions = [
            v for v in existing_versions.keys() 
            if v.startswith(date_prefix)
        ]
        
        if not same_date_versions:
            return f"{date_prefix}.1"
        
        max_seq = 0
        for v in same_date_versions:
            try:
                seq = int(v.split('.')[-1])
                max_seq = max(max_seq, seq)
            except:
                pass
        
        return f"{date_prefix}.{max_seq + 1}"
    
    def get_next_user_version(self, existing_versions: Dict[str, Any]) -> str:
        """Generate semantic version number (user-facing)"""
        if not existing_versions:
            return "1.1.0"
        
        # Find max minor version
        max_minor = 0
        for entry in existing_versions.values():
            if 'version' in entry:
                try:
                    # Parse version like "1.5.0" -> extract minor = 5
                    version_str = str(entry['version'])
                    parts = version_str.split('.')
                    if len(parts) >= 2:
                        minor = int(parts[1])
                        max_minor = max(max_minor, minor)
                except:
                    pass
        
        return f"1.{max_minor + 1}.0"
    
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
        
        # Sort versions by version key (date-based YYYY.MM.DD.N) descending
        if 'versions' in changelog:
            def parse_version(v):
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
        print(f'🚀 Generating changelog for branch: {self.branch_name}\n')
        
        # Check if we're on master
        if self.branch_name == self.base_branch:
            print(f'⚠ You are on {self.base_branch} branch. This script is meant for feature branches.')
            print('  Please run this from a feature branch or specify one with --branch')
            sys.exit(1)
        
        # Authenticate
        self.access_token = self.authenticate()
        
        # Get branch changes
        print(f'\n📁 Analyzing changes in {self.branch_name} compared to {self.base_branch}...')
        files = self.get_branch_changes()
        
        if not files:
            print('⚠ No content file changes found in this branch!')
            return
        
        print(f'✓ Found {len(files)} changed content files\n')
        
        # Get commit context from branch
        commit_messages = self.get_branch_commit_messages()
        commit_context = ' | '.join(commit_messages[:3])  # Use first 3 commits for context
        
        # Load existing changelog
        changelog = self.load_existing_changelog()
        
        # Generate version key and user version
        today = datetime.now().strftime('%Y-%m-%d')
        version_key = self.get_next_version(today, changelog.get('versions', {}))
        user_version = self.get_next_user_version(changelog.get('versions', {}))
        
        print(f'📝 Generating changelog entry: {version_key} (v{user_version})\n')
        
        # Build version entry
        version_entry = {
            'version': user_version,
            'date': today,
            'files': []
        }
        
        # Generate file-level descriptions with AI
        for idx, file in enumerate(files, 1):
            print(f'[{idx}/{len(files)}] Processing: {file["name"]} ({file["status"]})...')
            
            try:
                file_details = self.generate_file_details(file, commit_context)
                version_entry['files'].append({
                    'name': file['name'],
                    'category': file['category'],
                    'description': file_details['description'],
                    'change_type': file_details['change_type'],
                    'breaking_change': file_details['breaking_change']
                })
                print(f'  ✓ {file_details["description"]}')
            except Exception as e:
                print(f'  ✗ Error: {e}')
                # Add basic entry on error
                version_entry['files'].append({
                    'name': file['name'],
                    'category': file['category'],
                    'description': f"{file['status'].title()} {file['name']}",
                    'change_type': file['status'],
                    'breaking_change': False
                })
        
        # Add to changelog
        changelog['versions'][version_key] = version_entry
        
        # Save changelog
        print('\n💾 Saving changelog...')
        self.save_changelog(changelog)
        
        # Summary
        print('\n' + '=' * 60)
        print(f'✓ Created changelog entry: {version_key} (v{user_version})')
        print(f'✓ Files documented: {len(version_entry["files"])}')
        print('=' * 60)
        print(f'\n💡 Next steps:')
        print(f'  1. Review the changes in {OUTPUT_YAML}')
        print(f'  2. Commit the changelog files to your branch')
        print(f'  3. Create/update your merge request to {self.base_branch}')


def main():
    """Entry point"""
    parser = argparse.ArgumentParser(
        description='Generate changelog for feature branch changes',
        epilog='Examples:\n'
               '  %(prog)s                        # Analyze current branch\n'
               '  %(prog)s --branch feature-xyz   # Analyze specific branch',
        formatter_class=argparse.RawDescriptionHelpFormatter
    )
    
    parser.add_argument('-b', '--branch', type=str,
                        help='Branch name to analyze (default: current branch)')
    
    args = parser.parse_args()
    
    try:
        generator = BranchChangelogGenerator(branch_name=args.branch)
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
