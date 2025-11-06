#!/usr/bin/env python3
"""
Content Changelog Manager
Utility script to manage changelog entries for detectors, navigators, and groups.
"""

import json
import argparse
from datetime import datetime
from pathlib import Path
from typing import Dict, List, Optional


class ChangelogManager:
    """Manages changelog entries for content pieces."""
    
    CHANGE_TYPES = [
        "created",
        "updated",
        "metric_changed",
        "visualization_changed",
        "metadata_changed",
        "detector_rule_changed",
        "deprecated",
        "deleted",
        "migrated",
        "bug_fix",
        "performance_improvement"
    ]
    
    def __init__(self, changelog_path: str = "content_changelog.json"):
        """Initialize the changelog manager."""
        self.changelog_path = Path(changelog_path)
        self.changelog = self._load_changelog()
    
    def _load_changelog(self) -> Dict:
        """Load the changelog file."""
        if not self.changelog_path.exists():
            print(f"Warning: Changelog file not found at {self.changelog_path}")
            return self._create_empty_changelog()
        
        with open(self.changelog_path, 'r', encoding='utf-8') as f:
            return json.load(f)
    
    def _save_changelog(self):
        """Save the changelog file."""
        self.changelog['metadata']['last_updated'] = datetime.now().isoformat() + 'Z'
        
        with open(self.changelog_path, 'w', encoding='utf-8') as f:
            json.dump(self.changelog, f, indent=2, ensure_ascii=False)
        
        print(f"✓ Changelog saved to {self.changelog_path}")
    
    def _create_empty_changelog(self) -> Dict:
        """Create an empty changelog structure."""
        return {
            "metadata": {
                "version": "1.0.0",
                "last_updated": datetime.now().isoformat() + 'Z',
                "description": "Changelog tracking system for all content pieces"
            },
            "detectors": {},
            "navigators": {},
            "groups": {},
            "change_types": dict(zip(self.CHANGE_TYPES, [""]*len(self.CHANGE_TYPES)))
        }
    
    def add_change(
        self,
        content_type: str,
        content_id: str,
        content_name: str,
        change_type: str,
        description: str,
        version: str,
        author: str = "",
        files_modified: Optional[List[str]] = None,
        breaking_change: bool = False,
        notes: str = ""
    ):
        """Add a new changelog entry for a content piece."""
        
        if content_type not in ["detectors", "navigators", "groups"]:
            raise ValueError(f"Invalid content_type: {content_type}. Must be detectors, navigators, or groups.")
        
        if change_type not in self.CHANGE_TYPES:
            raise ValueError(f"Invalid change_type: {change_type}. Must be one of {self.CHANGE_TYPES}")
        
        # Initialize content if it doesn't exist
        if content_id not in self.changelog[content_type]:
            self.changelog[content_type][content_id] = {
                "name": content_name,
                "changes": []
            }
        
        # Create the change entry
        change_entry = {
            "version": version,
            "date": datetime.now().isoformat() + 'Z',
            "change_type": change_type,
            "description": description,
            "author": author,
            "files_modified": files_modified or [],
            "breaking_change": breaking_change,
            "notes": notes
        }
        
        # Add to the beginning of the changes array (most recent first)
        self.changelog[content_type][content_id]["changes"].insert(0, change_entry)
        
        # Update content name if it changed
        self.changelog[content_type][content_id]["name"] = content_name
        
        self._save_changelog()
        
        print(f"✓ Added {change_type} entry for {content_type[:-1]} '{content_name}' (ID: {content_id})")
    
    def get_history(self, content_type: str, content_id: str) -> List[Dict]:
        """Get the full change history for a content piece."""
        if content_type not in self.changelog:
            return []
        
        if content_id not in self.changelog[content_type]:
            return []
        
        return self.changelog[content_type][content_id].get("changes", [])
    
    def get_recent_changes(self, limit: int = 10, content_type: Optional[str] = None) -> List[Dict]:
        """Get the most recent changes across all or specific content types."""
        all_changes = []
        
        types_to_check = [content_type] if content_type else ["detectors", "navigators", "groups"]
        
        for ctype in types_to_check:
            if ctype not in self.changelog:
                continue
            
            for content_id, content_data in self.changelog[ctype].items():
                for change in content_data.get("changes", []):
                    all_changes.append({
                        "content_type": ctype,
                        "content_id": content_id,
                        "content_name": content_data["name"],
                        **change
                    })
        
        # Sort by date (most recent first)
        all_changes.sort(key=lambda x: x["date"], reverse=True)
        
        return all_changes[:limit]
    
    def print_history(self, content_type: str, content_id: str):
        """Print the change history for a content piece."""
        history = self.get_history(content_type, content_id)
        
        if not history:
            print(f"No history found for {content_type[:-1]} ID: {content_id}")
            return
        
        content_name = self.changelog[content_type][content_id]["name"]
        
        print(f"\n{'='*80}")
        print(f"Change History for: {content_name}")
        print(f"Type: {content_type[:-1].title()} | ID: {content_id}")
        print(f"{'='*80}\n")
        
        for i, change in enumerate(history, 1):
            print(f"{i}. Version {change['version']} - {change['date'][:10]}")
            print(f"   Type: {change['change_type']}")
            print(f"   Description: {change['description']}")
            if change.get('author'):
                print(f"   Author: {change['author']}")
            if change.get('breaking_change'):
                print(f"   ⚠️  BREAKING CHANGE")
            if change.get('files_modified'):
                print(f"   Files: {', '.join(change['files_modified'])}")
            if change.get('notes'):
                print(f"   Notes: {change['notes']}")
            print()
    
    def print_recent_changes(self, limit: int = 10, content_type: Optional[str] = None):
        """Print recent changes."""
        changes = self.get_recent_changes(limit, content_type)
        
        type_filter = f" for {content_type}" if content_type else ""
        print(f"\n{'='*80}")
        print(f"Recent Changes{type_filter} (Last {limit})")
        print(f"{'='*80}\n")
        
        for i, change in enumerate(changes, 1):
            breaking = " ⚠️ BREAKING" if change.get('breaking_change') else ""
            print(f"{i}. [{change['content_type'][:-1].upper()}] {change['content_name']}")
            print(f"   Version {change['version']} | {change['date'][:10]} | {change['change_type']}{breaking}")
            print(f"   {change['description']}")
            print()
    
    def export_history_to_markdown(self, content_type: str, content_id: str, output_path: str):
        """Export change history to a markdown file."""
        history = self.get_history(content_type, content_id)
        
        if not history:
            print(f"No history found for {content_type[:-1]} ID: {content_id}")
            return
        
        content_name = self.changelog[content_type][content_id]["name"]
        
        md_lines = [
            f"# Change History: {content_name}",
            "",
            f"**Type:** {content_type[:-1].title()}  ",
            f"**ID:** `{content_id}`  ",
            "",
            "---",
            ""
        ]
        
        for change in history:
            md_lines.append(f"## Version {change['version']} - {change['date'][:10]}")
            md_lines.append("")
            md_lines.append(f"**Change Type:** `{change['change_type']}`  ")
            
            if change.get('breaking_change'):
                md_lines.append(f"**⚠️ BREAKING CHANGE**  ")
            
            md_lines.append("")
            md_lines.append(f"**Description:**  ")
            md_lines.append(change['description'])
            md_lines.append("")
            
            if change.get('author'):
                md_lines.append(f"**Author:** {change['author']}  ")
            
            if change.get('files_modified'):
                md_lines.append("")
                md_lines.append("**Files Modified:**")
                for file in change['files_modified']:
                    md_lines.append(f"- `{file}`")
            
            if change.get('notes'):
                md_lines.append("")
                md_lines.append(f"**Notes:**  ")
                md_lines.append(change['notes'])
            
            md_lines.append("")
            md_lines.append("---")
            md_lines.append("")
        
        with open(output_path, 'w', encoding='utf-8') as f:
            f.write('\n'.join(md_lines))
        
        print(f"✓ Exported history to {output_path}")


def main():
    """Main CLI interface."""
    parser = argparse.ArgumentParser(description="Manage content changelog entries")
    subparsers = parser.add_subparsers(dest='command', help='Available commands')
    
    # Add change command
    add_parser = subparsers.add_parser('add', help='Add a new changelog entry')
    add_parser.add_argument('content_type', choices=['detectors', 'navigators', 'groups'])
    add_parser.add_argument('content_id', help='Content ID')
    add_parser.add_argument('content_name', help='Content name')
    add_parser.add_argument('version', help='Version number (e.g., 1.1.0)')
    add_parser.add_argument('change_type', choices=ChangelogManager.CHANGE_TYPES)
    add_parser.add_argument('description', help='Description of the change')
    add_parser.add_argument('--author', default='', help='Author of the change')
    add_parser.add_argument('--files', nargs='+', help='Files modified')
    add_parser.add_argument('--breaking', action='store_true', help='Mark as breaking change')
    add_parser.add_argument('--notes', default='', help='Additional notes')
    
    # History command
    history_parser = subparsers.add_parser('history', help='View change history')
    history_parser.add_argument('content_type', choices=['detectors', 'navigators', 'groups'])
    history_parser.add_argument('content_id', help='Content ID')
    
    # Recent command
    recent_parser = subparsers.add_parser('recent', help='View recent changes')
    recent_parser.add_argument('--limit', type=int, default=10, help='Number of recent changes to show')
    recent_parser.add_argument('--type', choices=['detectors', 'navigators', 'groups'], help='Filter by content type')
    
    # Export command
    export_parser = subparsers.add_parser('export', help='Export history to markdown')
    export_parser.add_argument('content_type', choices=['detectors', 'navigators', 'groups'])
    export_parser.add_argument('content_id', help='Content ID')
    export_parser.add_argument('output_path', help='Output markdown file path')
    
    args = parser.parse_args()
    
    if not args.command:
        parser.print_help()
        return
    
    manager = ChangelogManager()
    
    if args.command == 'add':
        manager.add_change(
            content_type=args.content_type,
            content_id=args.content_id,
            content_name=args.content_name,
            version=args.version,
            change_type=args.change_type,
            description=args.description,
            author=args.author,
            files_modified=args.files or [],
            breaking_change=args.breaking,
            notes=args.notes
        )
    
    elif args.command == 'history':
        manager.print_history(args.content_type, args.content_id)
    
    elif args.command == 'recent':
        manager.print_recent_changes(args.limit, args.type)
    
    elif args.command == 'export':
        manager.export_history_to_markdown(args.content_type, args.content_id, args.output_path)


if __name__ == '__main__':
    main()
