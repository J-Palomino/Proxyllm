#!/usr/bin/env python3
"""
Export LiteLLM database schema to CSV files
Each table gets its own CSV file with column headers
"""
import re
import csv
import os
from typing import List, Dict, Any
from datetime import datetime

def parse_prisma_schema(schema_file: str) -> Dict[str, List[Dict[str, Any]]]:
    """Parse Prisma schema file and extract table definitions"""
    
    with open(schema_file, 'r') as f:
        content = f.read()
    
    tables = {}
    
    # Regex to match model definitions
    model_pattern = re.compile(r'model\s+(\w+)\s*\{([^}]+)\}', re.DOTALL)
    
    for match in model_pattern.finditer(content):
        table_name = match.group(1)
        table_body = match.group(2).strip()
        
        columns = []
        
        # Parse each line in the table body
        for line in table_body.split('\n'):
            line = line.strip()
            
            # Skip comments and empty lines
            if not line or line.startswith('//') or line.startswith('@@'):
                continue
                
            # Parse field definitions
            # Format: field_name Type modifiers
            parts = line.split()
            if len(parts) >= 2:
                field_name = parts[0]
                field_type = parts[1]
                
                # Extract modifiers (optional, default values, etc.)
                modifiers = []
                if len(parts) > 2:
                    modifiers = parts[2:]
                
                # Determine if field is required/optional
                is_optional = '?' in field_type
                is_array = '[]' in field_type
                is_id = '@id' in ' '.join(modifiers)
                is_unique = '@unique' in ' '.join(modifiers)
                
                # Extract default value
                default_value = None
                for modifier in modifiers:
                    if modifier.startswith('@default('):
                        default_match = re.search(r'@default\(([^)]+)\)', modifier)
                        if default_match:
                            default_value = default_match.group(1)
                
                # Clean up type
                clean_type = field_type.replace('?', '').replace('[]', '')
                
                columns.append({
                    'field_name': field_name,
                    'type': clean_type,
                    'is_optional': is_optional,
                    'is_array': is_array,
                    'is_id': is_id,
                    'is_unique': is_unique,
                    'default_value': default_value,
                    'raw_definition': line
                })
        
        if columns:  # Only add tables that have columns
            tables[table_name] = columns
    
    return tables

def export_to_csv(tables: Dict[str, List[Dict[str, Any]]], output_dir: str = 'schema_export'):
    """Export each table to a separate CSV file"""
    
    # Create output directory
    if not os.path.exists(output_dir):
        os.makedirs(output_dir)
    
    # Create a summary file with all tables
    summary_file = os.path.join(output_dir, '00_schema_summary.csv')
    with open(summary_file, 'w', newline='', encoding='utf-8') as f:
        writer = csv.writer(f)
        writer.writerow(['Table Name', 'Column Count', 'Primary Key Fields', 'Export File'])
        
        for table_name, columns in tables.items():
            primary_keys = [col['field_name'] for col in columns if col['is_id']]
            pk_str = ', '.join(primary_keys) if primary_keys else 'None'
            writer.writerow([table_name, len(columns), pk_str, f'{table_name}.csv'])
    
    # Export each table to its own CSV
    for table_name, columns in tables.items():
        filename = os.path.join(output_dir, f'{table_name}.csv')
        
        with open(filename, 'w', newline='', encoding='utf-8') as f:
            writer = csv.writer(f)
            
            # Write headers
            headers = [
                'Field Name',
                'Type',
                'Required',
                'Array',
                'Primary Key',
                'Unique',
                'Default Value',
                'Raw Definition'
            ]
            writer.writerow(headers)
            
            # Write column data
            for col in columns:
                writer.writerow([
                    col['field_name'],
                    col['type'],
                    'No' if col['is_optional'] else 'Yes',
                    'Yes' if col['is_array'] else 'No',
                    'Yes' if col['is_id'] else 'No',
                    'Yes' if col['is_unique'] else 'No',
                    col['default_value'] or '',
                    col['raw_definition']
                ])
    
    return len(tables)

def main():
    """Main function to export schema"""
    schema_file = 'litellm/proxy/schema.prisma'
    
    if not os.path.exists(schema_file):
        print(f"Schema file not found: {schema_file}")
        return
    
    print("Parsing Prisma schema...")
    tables = parse_prisma_schema(schema_file)
    
    print(f"Found {len(tables)} tables:")
    for table_name in sorted(tables.keys()):
        column_count = len(tables[table_name])
        print(f"  - {table_name}: {column_count} columns")
    
    print("\nExporting to CSV files...")
    exported_count = export_to_csv(tables)
    
    print(f"\nExport complete!")
    print(f"- Exported {exported_count} tables to CSV files")
    print(f"- Files saved in 'schema_export/' directory")
    print(f"- Summary file: schema_export/00_schema_summary.csv")
    
    # Create an Excel-style index file
    index_file = 'schema_export/00_table_index.csv'
    with open(index_file, 'w', newline='', encoding='utf-8') as f:
        writer = csv.writer(f)
        writer.writerow(['#', 'Table Name', 'Description', 'Key Fields'])
        
        descriptions = {
            'LiteLLM_BudgetTable': 'Budget and rate limits for organizations',
            'LiteLLM_CredentialsTable': 'API credentials for different providers',
            'LiteLLM_ProxyModelTable': 'Model configurations and parameters', 
            'LiteLLM_OrganizationTable': 'Organization management and settings',
            'LiteLLM_ModelTable': 'Model aliases and team associations',
            'LiteLLM_TeamTable': 'Team management and permissions',
            'LiteLLM_UserTable': 'User accounts and access control',
            'LiteLLM_ObjectPermissionTable': 'Object-level permissions',
            'LiteLLM_MCPServerTable': 'MCP server configurations',
            'LiteLLM_VerificationToken': 'API keys and access tokens',
            'LiteLLM_EndUserTable': 'End user management and limits',
            'LiteLLM_Config': 'Proxy configuration storage',
            'LiteLLM_SpendLogs': 'Request spending and usage logs',
            'LiteLLM_ErrorLogs': 'Error tracking and debugging',
            'LiteLLM_UserNotifications': 'User notification system',
            'LiteLLM_TeamMembership': 'Team membership tracking',
            'LiteLLM_OrganizationMembership': 'Organization membership',
            'LiteLLM_InvitationLink': 'Invitation link management',
            'LiteLLM_AuditLog': 'Audit trail for changes',
            'LiteLLM_DailyUserSpend': 'Daily user spending metrics',
            'LiteLLM_DailyTeamSpend': 'Daily team spending metrics',
            'LiteLLM_DailyTagSpend': 'Daily tag-based spending metrics',
            'LiteLLM_CronJob': 'Cron job management',
            'LiteLLM_ManagedFileTable': 'File management',
            'LiteLLM_ManagedObjectTable': 'Object management for batches/fine-tuning',
            'LiteLLM_ManagedVectorStoresTable': 'Vector store management',
            'LiteLLM_GuardrailsTable': 'Guardrail configurations',
            'LiteLLM_PromptTable': 'Prompt configurations',
            'LiteLLM_HealthCheckTable': 'Model health check tracking'
        }
        
        for i, (table_name, columns) in enumerate(sorted(tables.items()), 1):
            key_fields = [col['field_name'] for col in columns if col['is_id'] or col['is_unique']]
            writer.writerow([
                i,
                table_name,
                descriptions.get(table_name, 'Database table'),
                ', '.join(key_fields[:3])  # Show first 3 key fields
            ])

if __name__ == '__main__':
    main()