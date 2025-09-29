#!/usr/bin/env python3
"""
Zed Conversation History Exporter for Spyder Project
====================================================

This script exports conversation history from Zed's SQLite database
to readable markdown files for easy reference and documentation.

Author: Claude AI Assistant
Date: 2024
Project: Spyder Trading System
"""

import sqlite3
import json
import os
import sys
from datetime import datetime
from pathlib import Path
import argparse
from collections import defaultdict


class ZedConversationExporter:
    def __init__(self, db_path=None):
        """Initialize the exporter with database path."""
        if db_path is None:
            home = Path.home()
            self.db_path = home / ".local/share/zed/threads/threads.db"
        else:
            self.db_path = Path(db_path)

        self.output_dir = Path("docs/conversation_history")
        self.output_dir.mkdir(parents=True, exist_ok=True)

    def check_database_exists(self):
        """Check if the Zed database exists."""
        if not self.db_path.exists():
            print(f"❌ Database not found at: {self.db_path}")
            print("Make sure Zed is installed and has been used for conversations.")
            return False
        return True

    def get_conversations(self):
        """Retrieve all conversations from the database."""
        try:
            conn = sqlite3.connect(str(self.db_path))
            cursor = conn.cursor()

            cursor.execute("""
                SELECT id, summary, updated_at, data_type, data
                FROM threads
                ORDER BY updated_at DESC
            """)

            conversations = cursor.fetchall()
            conn.close()

            print(f"✅ Found {len(conversations)} conversations")
            return conversations

        except sqlite3.Error as e:
            print(f"❌ Database error: {e}")
            return []

    def parse_conversation_data(self, data_blob, data_type):
        """Parse the binary conversation data."""
        try:
            if data_type == "json":
                # Try to decode as UTF-8 JSON
                json_str = data_blob.decode('utf-8')
                return json.loads(json_str)
            else:
                # Handle other data types
                return {"raw_data": data_blob.hex(), "type": data_type}
        except Exception as e:
            print(f"⚠️  Warning: Could not parse data - {e}")
            return {"error": str(e), "type": data_type}

    def format_timestamp(self, timestamp_str):
        """Format the timestamp for display."""
        try:
            # Parse ISO timestamp
            dt = datetime.fromisoformat(timestamp_str.replace('Z', '+00:00'))
            return dt.strftime('%Y-%m-%d %H:%M:%S UTC')
        except:
            return timestamp_str

    def extract_messages(self, conversation_data):
        """Extract messages from conversation data structure."""
        messages = []

        if isinstance(conversation_data, dict):
            # Look for common message structures
            if 'messages' in conversation_data:
                messages = conversation_data['messages']
            elif 'thread' in conversation_data and 'messages' in conversation_data['thread']:
                messages = conversation_data['thread']['messages']
            elif 'conversation' in conversation_data:
                messages = conversation_data['conversation']

        return messages

    def generate_reference_id(self, conversations_by_date, updated_at, conv_id):
        """Generate a reference ID like Chat-2025-09-23-A."""
        date_str = updated_at[:10]  # Get YYYY-MM-DD

        # Get conversations for this date, sorted by time
        date_conversations = conversations_by_date[date_str]

        # Find the position of this conversation (0-based)
        position = next(i for i, (cid, _, _) in enumerate(date_conversations) if cid == conv_id)

        # Convert to letter (A, B, C, etc.)
        letter = chr(ord('A') + position)

        return f"Chat-{date_str}-{letter}"

    def export_conversation_to_markdown(self, conv_id, summary, updated_at, data, reference_id):
        """Export a single conversation to markdown."""
        # Create safe filename using reference ID
        filename = f"{reference_id}.md"
        filepath = self.output_dir / filename

        timestamp = self.format_timestamp(updated_at)
        with open(filepath, 'w', encoding='utf-8') as f:
            f.write(f"# {summary}\n\n")
            f.write(f"**Reference ID:** `{reference_id}`  \n")
            f.write(f"**Conversation ID:** `{conv_id}`  \n")
            f.write(f"**Last Updated:** {timestamp}  \n")
            f.write(f"**Export Date:** {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n\n")
            f.write("---\n\n")

            messages = self.extract_messages(data)

            if messages:
                f.write("## Conversation Messages\n\n")
                for i, msg in enumerate(messages, 1):
                    if isinstance(msg, dict):
                        role = msg.get('role', 'unknown')
                        content = msg.get('content', str(msg))

                        f.write(f"### Message {i} - {role.title()}\n\n")
                        f.write(f"{content}\n\n")
                        f.write("---\n\n")
            else:
                f.write("## Raw Conversation Data\n\n")
                f.write("```json\n")
                f.write(json.dumps(data, indent=2, default=str))
                f.write("\n```\n\n")

        return filepath

    def group_conversations_by_date(self, conversations):
        """Group conversations by date and assign reference IDs."""
        conversations_by_date = defaultdict(list)

        # Group by date, maintaining chronological order
        for conv_id, summary, updated_at, data_type, data_blob in conversations:
            date_str = updated_at[:10]
            conversations_by_date[date_str].append((conv_id, summary, updated_at))

        # Sort each date's conversations by time (earliest first for A, B, C...)
        for date in conversations_by_date:
            conversations_by_date[date].sort(key=lambda x: x[2])

        return conversations_by_date

    def export_all_conversations(self):
        """Export all conversations to markdown files."""
        if not self.check_database_exists():
            return False

        conversations = self.get_conversations()
        if not conversations:
            print("❌ No conversations found")
            return False

        # Group conversations by date for reference ID generation
        conversations_by_date = self.group_conversations_by_date(conversations)

        print(f"📁 Exporting to: {self.output_dir}")
        exported_count = 0

        for conv_id, summary, updated_at, data_type, data_blob in conversations:
            try:
                # Generate reference ID
                reference_id = self.generate_reference_id(conversations_by_date, updated_at, conv_id)

                # Parse conversation data
                conversation_data = self.parse_conversation_data(data_blob, data_type)

                # Export to markdown
                filepath = self.export_conversation_to_markdown(
                    conv_id, summary, updated_at, conversation_data, reference_id
                )

                print(f"✅ Exported: {reference_id} - {summary}")
                exported_count += 1

            except Exception as e:
                print(f"❌ Error exporting {summary}: {e}")

        print(f"\n🎉 Successfully exported {exported_count} conversations!")
        return True

    def create_index(self):
        """Create an index file listing all exported conversations."""
        conversations = self.get_conversations()
        if not conversations:
            return

        # Group conversations for reference ID generation
        conversations_by_date = self.group_conversations_by_date(conversations)

        index_path = self.output_dir / "README.md"
        lookup_path = self.output_dir / "conversation_lookup.md"

        with open(index_path, 'w', encoding='utf-8') as f:
            f.write("# Spyder Conversation History Index\n\n")
            f.write(f"**Generated:** {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}  \n")
            f.write(f"**Total Conversations:** {len(conversations)}\n\n")
            f.write("---\n\n")

            f.write("## Quick Reference\n\n")
            f.write("Use these reference IDs to quickly identify conversations:\n\n")

            # Group and display by date
            for date_str in sorted(conversations_by_date.keys(), reverse=True):
                f.write(f"### {date_str}\n\n")
                for i, (conv_id, summary, updated_at) in enumerate(conversations_by_date[date_str]):
                    reference_id = self.generate_reference_id(conversations_by_date, updated_at, conv_id)
                    timestamp = self.format_timestamp(updated_at)
                    f.write(f"- **{reference_id}**: [{summary}]({reference_id}.md) ({timestamp})\n")
                f.write("\n")

            f.write("---\n\n")
            f.write("## How to Reference Conversations\n\n")
            f.write("When talking to Claude, you can say:\n\n")
            f.write('- "Please reference Chat-2025-09-23-A for context"\n')
            f.write('- "In Chat-2025-09-23-B, we discussed..."\n')
            f.write('- "Building on Chat-2025-09-22-A..."\n\n')
            f.write("Then copy the relevant sections from that conversation file.\n\n")

        # Create a lookup table file
        with open(lookup_path, 'w', encoding='utf-8') as f:
            f.write("# Conversation Reference Lookup\n\n")
            f.write("Quick lookup table for conversation references:\n\n")
            f.write("| Reference ID | Summary | Date | File |\n")
            f.write("|--------------|---------|------|------|\n")

            for conv_id, summary, updated_at, data_type, data_blob in conversations:
                reference_id = self.generate_reference_id(conversations_by_date, updated_at, conv_id)
                timestamp = self.format_timestamp(updated_at)
                # Truncate summary for table
                short_summary = summary[:50] + "..." if len(summary) > 50 else summary
                f.write(f"| {reference_id} | {short_summary} | {timestamp} | [{reference_id}.md]({reference_id}.md) |\n")

        print(f"📋 Created index: {index_path}")
        print(f"🔍 Created lookup: {lookup_path}")


def main():
    """Main function with command line interface."""
    parser = argparse.ArgumentParser(
        description="Export Zed conversation history to markdown files",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  python export_zed_conversations.py                    # Export all conversations
  python export_zed_conversations.py --db-path /custom/path/threads.db
  python export_zed_conversations.py --list            # Just list conversations
        """
    )

    parser.add_argument(
        '--db-path',
        help='Path to Zed threads database (default: ~/.local/share/zed/threads/threads.db)'
    )

    parser.add_argument(
        '--list',
        action='store_true',
        help='Just list conversations without exporting'
    )

    parser.add_argument(
        '--output-dir',
        default='docs/conversation_history',
        help='Output directory for exported conversations'
    )

    args = parser.parse_args()

    print("🕷️  Spyder Conversation History Exporter")
    print("=" * 50)

    exporter = ZedConversationExporter(args.db_path)
    exporter.output_dir = Path(args.output_dir)
    exporter.output_dir.mkdir(parents=True, exist_ok=True)

    if args.list:
        # Just list conversations
        conversations = exporter.get_conversations()
        if conversations:
            print("\n📋 Available Conversations:")
            print("-" * 30)
            conversations_by_date = exporter.group_conversations_by_date(conversations)
            for conv_id, summary, updated_at, _, _ in conversations:
                reference_id = exporter.generate_reference_id(conversations_by_date, updated_at, conv_id)
                timestamp = exporter.format_timestamp(updated_at)
                print(f"• {reference_id}: {summary}")
                print(f"  Time: {timestamp}")
                print(f"  File: {reference_id}.md")
                print()
    else:
        # Export all conversations
        success = exporter.export_all_conversations()
        if success:
            exporter.create_index()
            print(f"\n📁 All files saved to: {exporter.output_dir}")
            print("\n💡 Tips:")
            print("- Use reference IDs like 'Chat-2025-09-23-A' when talking to Claude")
            print("- Check conversation_lookup.md for quick reference")
            print("- Copy relevant sections from conversation files for context")
            print("- The index shows all conversations organized by date")


if __name__ == "__main__":
    main()
