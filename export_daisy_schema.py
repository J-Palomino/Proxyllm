#!/usr/bin/env python3
"""
Export Daisy database schema (TypeORM entities) to CSV files
"""
import re
import csv
import os
import glob
from typing import List, Dict, Any
from datetime import datetime

def parse_typeorm_entity(file_path: str) -> Dict[str, Any]:
    """Parse a TypeORM entity file and extract schema information"""
    
    with open(file_path, 'r', encoding='utf-8') as f:
        content = f.read()
    
    # Extract entity name from the class definition
    entity_class_match = re.search(r'export\s+class\s+(\w+)', content)
    if not entity_class_match:
        return None
    
    entity_name = entity_class_match.group(1)
    
    # Find the table name from @Entity decorator
    table_name_match = re.search(r'@Entity\(\s*[\'"]([^\'"]+)[\'"]', content)
    table_name = table_name_match.group(1) if table_name_match else entity_name.lower()
    
    columns = []
    
    # Find all column definitions
    # Pattern for property with decorators
    property_pattern = re.compile(
        r'(@(?:PrimaryGeneratedColumn|Column|CreateDateColumn|UpdateDateColumn|ManyToOne|OneToMany|OneToOne|ManyToMany)[^\n]*\n(?:\s*@[^\n]*\n)*)\s*(\w+)(?:\?)?:\s*([^;\n]+)',
        re.MULTILINE | re.DOTALL
    )
    
    for match in property_pattern.finditer(content):
        decorators = match.group(1).strip()
        field_name = match.group(2)
        field_type = match.group(3).strip()
        
        # Parse decorators to extract column information
        is_primary = '@PrimaryGeneratedColumn' in decorators or '@PrimaryColumn' in decorators
        is_nullable = '?' in match.group(0) or 'nullable: true' in decorators
        is_unique = 'unique: true' in decorators
        is_relation = any(rel in decorators for rel in ['@ManyToOne', '@OneToMany', '@OneToOne', '@ManyToMany'])
        
        # Extract column type from @Column decorator
        column_type_match = re.search(r'@Column\(\s*[\'"]?([^\'"]+)[\'"]?', decorators)
        if column_type_match:
            db_type = column_type_match.group(1).split(',')[0].strip()
        else:
            db_type = 'text'  # default
        
        # Extract default value
        default_value = None
        default_match = re.search(r'default:\s*[\'"]?([^\'",}]+)[\'"]?', decorators)
        if default_match:
            default_value = default_match.group(1)
        
        # Check for auto-generated timestamps
        is_create_date = '@CreateDateColumn' in decorators
        is_update_date = '@UpdateDateColumn' in decorators
        
        if is_create_date:
            db_type = 'timestamp'
            default_value = 'CURRENT_TIMESTAMP'
        elif is_update_date:
            db_type = 'timestamp'
            default_value = 'CURRENT_TIMESTAMP ON UPDATE'
        
        columns.append({
            'field_name': field_name,
            'type': field_type,
            'db_type': db_type,
            'is_primary': is_primary,
            'is_nullable': is_nullable,
            'is_unique': is_unique,
            'is_relation': is_relation,
            'default_value': default_value,
            'decorators': decorators,
            'raw_definition': match.group(0)
        })
    
    return {
        'entity_name': entity_name,
        'table_name': table_name,
        'columns': columns,
        'file_path': file_path
    }

def export_daisy_schema_to_csv(entities: List[Dict], output_dir: str = 'daisy_schema_export'):
    """Export Daisy schema to CSV files"""
    
    # Create output directory
    if not os.path.exists(output_dir):
        os.makedirs(output_dir)
    
    # Create summary file
    summary_file = os.path.join(output_dir, '00_daisy_schema_summary.csv')
    with open(summary_file, 'w', newline='', encoding='utf-8') as f:
        writer = csv.writer(f)
        writer.writerow(['Entity Name', 'Table Name', 'Column Count', 'Primary Key Fields', 'Export File'])
        
        for entity in entities:
            primary_keys = [col['field_name'] for col in entity['columns'] if col['is_primary']]
            pk_str = ', '.join(primary_keys) if primary_keys else 'None'
            writer.writerow([
                entity['entity_name'],
                entity['table_name'],
                len(entity['columns']),
                pk_str,
                f"{entity['entity_name']}.csv"
            ])
    
    # Export each entity to its own CSV
    for entity in entities:
        filename = os.path.join(output_dir, f"{entity['entity_name']}.csv")
        
        with open(filename, 'w', newline='', encoding='utf-8') as f:
            writer = csv.writer(f)
            
            # Write headers
            headers = [
                'Field Name',
                'TypeScript Type',
                'Database Type',
                'Primary Key',
                'Nullable',
                'Unique',
                'Relation',
                'Default Value',
                'Decorators'
            ]
            writer.writerow(headers)
            
            # Write column data
            for col in entity['columns']:
                writer.writerow([
                    col['field_name'],
                    col['type'],
                    col['db_type'],
                    'Yes' if col['is_primary'] else 'No',
                    'Yes' if col['is_nullable'] else 'No',
                    'Yes' if col['is_unique'] else 'No',
                    'Yes' if col['is_relation'] else 'No',
                    col['default_value'] or '',
                    col['decorators'].replace('\n', ' ').strip()
                ])
    
    return len(entities)

def main():
    """Main function to export Daisy schema"""
    daisy_entities_path = '../daisy/packages/server/src/database/entities/'
    
    if not os.path.exists(daisy_entities_path):
        print(f"Daisy entities directory not found: {daisy_entities_path}")
        return
    
    print("Parsing Daisy TypeORM entities...")
    entities = []
    
    # Find all entity files
    entity_files = glob.glob(os.path.join(daisy_entities_path, '*.ts'))
    entity_files = [f for f in entity_files if not f.endswith('index.ts')]
    
    for file_path in entity_files:
        try:
            entity = parse_typeorm_entity(file_path)
            if entity and entity['columns']:  # Only include entities with columns
                entities.append(entity)
                print(f"  - {entity['entity_name']}: {len(entity['columns'])} columns")
        except Exception as e:
            print(f"  - Error parsing {file_path}: {e}")
    
    if not entities:
        print("No entities found!")
        return
    
    print(f"\nFound {len(entities)} entities total")
    
    print("\nExporting to CSV files...")
    exported_count = export_daisy_schema_to_csv(entities)
    
    print(f"\nDaisy schema export complete!")
    print(f"- Exported {exported_count} entities to CSV files")
    print(f"- Files saved in 'daisy_schema_export/' directory")
    print(f"- Summary file: daisy_schema_export/00_daisy_schema_summary.csv")
    
    # Create index file with descriptions
    index_file = 'daisy_schema_export/00_daisy_table_index.csv'
    with open(index_file, 'w', newline='', encoding='utf-8') as f:
        writer = csv.writer(f)
        writer.writerow(['#', 'Entity Name', 'Table Name', 'Description', 'Column Count'])
        
        descriptions = {
            'ApiKey': 'API key management for authentication',
            'Assistant': 'AI assistant configurations',
            'ChatFlow': 'Chat flow definitions and workflows',
            'ChatMessage': 'Chat message history and content',
            'ChatMessageFeedback': 'User feedback on chat messages',
            'Credential': 'Stored credentials for various services',
            'CustomTemplate': 'Custom templates for workflows',
            'Dataset': 'Dataset management for training/evaluation',
            'DatasetRow': 'Individual rows within datasets',
            'DocumentStore': 'Document storage and management',
            'DocumentStoreFileChunk': 'File chunks for document processing',
            'Evaluation': 'Evaluation configurations and settings',
            'EvaluationRun': 'Individual evaluation run instances',
            'Evaluator': 'Evaluator configurations',
            'Execution': 'Execution logs and tracking',
            'Lead': 'Lead management and tracking',
            'PhoneNumber': 'Phone number management',
            'ScheduledTask': 'Scheduled task management',
            'Tool': 'Tool definitions and configurations',
            'UpsertHistory': 'History of upsert operations',
            'User': 'User account management',
            'Variable': 'Variable definitions for workflows'
        }
        
        for i, entity in enumerate(sorted(entities, key=lambda x: x['entity_name']), 1):
            writer.writerow([
                i,
                entity['entity_name'],
                entity['table_name'],
                descriptions.get(entity['entity_name'], 'Database entity'),
                len(entity['columns'])
            ])

if __name__ == '__main__':
    main()