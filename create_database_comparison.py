#!/usr/bin/env python3
"""
Create side-by-side comparison of LiteLLM and Daisy database schemas
"""
import csv
import os
import json
from typing import Dict, List, Any, Set
from difflib import SequenceMatcher

def load_schema_summaries():
    """Load both schema summaries"""
    
    # Load LiteLLM schema
    litellm_tables = {}
    litellm_summary_file = 'schema_export/00_schema_summary.csv'
    if os.path.exists(litellm_summary_file):
        with open(litellm_summary_file, 'r', encoding='utf-8') as f:
            reader = csv.DictReader(f)
            for row in reader:
                litellm_tables[row['Table Name']] = {
                    'column_count': int(row['Column Count']),
                    'primary_keys': row['Primary Key Fields'],
                    'type': 'LiteLLM'
                }
    
    # Load Daisy schema
    daisy_tables = {}
    daisy_summary_file = 'daisy_schema_export/00_daisy_schema_summary.csv'
    if os.path.exists(daisy_summary_file):
        with open(daisy_summary_file, 'r', encoding='utf-8') as f:
            reader = csv.DictReader(f)
            for row in reader:
                # Use Entity Name as the key for consistency
                daisy_tables[row['Entity Name']] = {
                    'table_name': row['Table Name'],
                    'column_count': int(row['Column Count']),
                    'primary_keys': row['Primary Key Fields'],
                    'type': 'Daisy'
                }
    
    return litellm_tables, daisy_tables

def find_similar_tables(litellm_tables: Dict, daisy_tables: Dict, threshold: float = 0.4) -> List[Dict]:
    """Find tables that might serve similar purposes"""
    
    similar_pairs = []
    
    for litellm_name, litellm_info in litellm_tables.items():
        best_match = None
        best_score = 0
        
        for daisy_name, daisy_info in daisy_tables.items():
            # Compare table names (remove prefixes for better matching)
            clean_litellm = litellm_name.replace('LiteLLM_', '').lower()
            clean_daisy = daisy_name.lower()
            
            # Calculate similarity score
            score = SequenceMatcher(None, clean_litellm, clean_daisy).ratio()
            
            # Also check for semantic similarity
            semantic_keywords = {
                'user': ['user', 'account', 'profile'],
                'team': ['team', 'group', 'organization'],
                'key': ['key', 'token', 'credential', 'apikey'],
                'spend': ['spend', 'usage', 'billing', 'cost'],
                'log': ['log', 'history', 'audit', 'record'],
                'model': ['model', 'assistant', 'llm'],
                'config': ['config', 'setting', 'variable'],
                'budget': ['budget', 'limit', 'quota']
            }
            
            for concept, keywords in semantic_keywords.items():
                if any(kw in clean_litellm for kw in keywords) and any(kw in clean_daisy for kw in keywords):
                    score += 0.3
            
            if score > best_score and score >= threshold:
                best_score = score
                best_match = {
                    'daisy_name': daisy_name,
                    'daisy_info': daisy_info,
                    'similarity_score': score
                }
        
        if best_match:
            similar_pairs.append({
                'litellm_name': litellm_name,
                'litellm_info': litellm_info,
                'daisy_name': best_match['daisy_name'],
                'daisy_info': best_match['daisy_info'],
                'similarity_score': best_match['similarity_score']
            })
    
    return sorted(similar_pairs, key=lambda x: x['similarity_score'], reverse=True)

def create_comparison_report():
    """Create comprehensive comparison report"""
    
    print("Loading schemas...")
    litellm_tables, daisy_tables = load_schema_summaries()
    
    print(f"Found {len(litellm_tables)} LiteLLM tables and {len(daisy_tables)} Daisy entities")
    
    # Create comparison directory
    comparison_dir = 'database_comparison'
    if not os.path.exists(comparison_dir):
        os.makedirs(comparison_dir)
    
    # 1. Overall Statistics Comparison
    stats_file = os.path.join(comparison_dir, '01_overall_statistics.csv')
    with open(stats_file, 'w', newline='', encoding='utf-8') as f:
        writer = csv.writer(f)
        writer.writerow(['Metric', 'LiteLLM (Prisma)', 'Daisy (TypeORM)'])
        
        litellm_total_columns = sum(info['column_count'] for info in litellm_tables.values())
        daisy_total_columns = sum(info['column_count'] for info in daisy_tables.values())
        
        writer.writerow(['Total Tables/Entities', len(litellm_tables), len(daisy_tables)])
        writer.writerow(['Total Columns/Fields', litellm_total_columns, daisy_total_columns])
        writer.writerow(['Average Columns per Table', f"{litellm_total_columns/len(litellm_tables):.1f}", f"{daisy_total_columns/len(daisy_tables):.1f}"])
        writer.writerow(['ORM Technology', 'Prisma (PostgreSQL)', 'TypeORM (Multi-DB)'])
        writer.writerow(['Primary Focus', 'LLM Proxy & Usage Tracking', 'Workflow & Assistant Management'])
    
    # 2. Side-by-Side Table Listing
    tables_file = os.path.join(comparison_dir, '02_all_tables_comparison.csv')
    with open(tables_file, 'w', newline='', encoding='utf-8') as f:
        writer = csv.writer(f)
        writer.writerow(['LiteLLM Table', 'LiteLLM Columns', 'LiteLLM Primary Key', 'Daisy Entity', 'Daisy Columns', 'Daisy Primary Key'])
        
        all_litellm = sorted(litellm_tables.keys())
        all_daisy = sorted(daisy_tables.keys())
        max_rows = max(len(all_litellm), len(all_daisy))
        
        for i in range(max_rows):
            litellm_name = all_litellm[i] if i < len(all_litellm) else ''
            litellm_cols = str(litellm_tables[all_litellm[i]]['column_count']) if i < len(all_litellm) else ''
            litellm_pk = litellm_tables[all_litellm[i]]['primary_keys'] if i < len(all_litellm) else ''
            
            daisy_name = all_daisy[i] if i < len(all_daisy) else ''
            daisy_cols = str(daisy_tables[all_daisy[i]]['column_count']) if i < len(all_daisy) else ''
            daisy_pk = daisy_tables[all_daisy[i]]['primary_keys'] if i < len(all_daisy) else ''
            
            writer.writerow([litellm_name, litellm_cols, litellm_pk, daisy_name, daisy_cols, daisy_pk])
    
    # 3. Similar Tables Analysis
    print("Finding similar tables...")
    similar_pairs = find_similar_tables(litellm_tables, daisy_tables)
    
    similar_file = os.path.join(comparison_dir, '03_similar_tables.csv')
    with open(similar_file, 'w', newline='', encoding='utf-8') as f:
        writer = csv.writer(f)
        writer.writerow(['LiteLLM Table', 'LiteLLM Cols', 'Daisy Entity', 'Daisy Cols', 'Similarity Score', 'Analysis'])
        
        for pair in similar_pairs:
            analysis = []
            
            # Column count comparison
            litellm_cols = pair['litellm_info']['column_count']
            daisy_cols = pair['daisy_info']['column_count']
            
            if abs(litellm_cols - daisy_cols) <= 2:
                analysis.append("Similar complexity")
            elif litellm_cols > daisy_cols:
                analysis.append("LiteLLM more complex")
            else:
                analysis.append("Daisy more complex")
            
            # Primary key analysis
            if 'id' in pair['litellm_info']['primary_keys'].lower() and 'id' in pair['daisy_info']['primary_keys'].lower():
                analysis.append("Similar PK pattern")
            
            writer.writerow([
                pair['litellm_name'],
                litellm_cols,
                pair['daisy_name'],
                daisy_cols,
                f"{pair['similarity_score']:.2f}",
                '; '.join(analysis)
            ])
    
    # 4. Unique Tables Analysis
    unique_file = os.path.join(comparison_dir, '04_unique_tables.csv')
    with open(unique_file, 'w', newline='', encoding='utf-8') as f:
        writer = csv.writer(f)
        writer.writerow(['Table/Entity Name', 'Project', 'Columns', 'Purpose Category', 'Unique Features'])
        
        # Find tables that don't have matches
        matched_litellm = set(pair['litellm_name'] for pair in similar_pairs)
        matched_daisy = set(pair['daisy_name'] for pair in similar_pairs)
        
        unique_litellm = set(litellm_tables.keys()) - matched_litellm
        unique_daisy = set(daisy_tables.keys()) - matched_daisy
        
        # Categorize unique tables
        categories = {
            'user_management': ['user', 'team', 'organization', 'member'],
            'billing_tracking': ['spend', 'budget', 'billing', 'daily'],
            'api_management': ['key', 'token', 'credential', 'verification'],
            'content_management': ['message', 'chat', 'document', 'template'],
            'workflow_management': ['flow', 'execution', 'task', 'evaluation'],
            'system_management': ['config', 'audit', 'log', 'health', 'cron'],
            'ai_specific': ['model', 'assistant', 'prompt', 'guardrail', 'mcp']
        }
        
        def categorize_table(table_name):
            table_lower = table_name.lower()
            for category, keywords in categories.items():
                if any(keyword in table_lower for keyword in keywords):
                    return category.replace('_', ' ').title()
            return 'Other'
        
        # Write unique LiteLLM tables
        for table in sorted(unique_litellm):
            info = litellm_tables[table]
            purpose = categorize_table(table)
            features = []
            
            if 'Budget' in table:
                features.append('Budget limits & tracking')
            elif 'Spend' in table or 'Daily' in table:
                features.append('Usage analytics & metrics')
            elif 'Verification' in table:
                features.append('API key management')
            elif 'MCP' in table:
                features.append('Model Context Protocol support')
            elif 'Guardrail' in table:
                features.append('AI safety & content filtering')
            
            writer.writerow([table, 'LiteLLM', info['column_count'], purpose, '; '.join(features)])
        
        # Write unique Daisy tables
        for table in sorted(unique_daisy):
            info = daisy_tables[table]
            purpose = categorize_table(table)
            features = []
            
            if 'Chat' in table:
                features.append('Conversational AI features')
            elif 'Document' in table:
                features.append('Document processing & storage')
            elif 'Evaluation' in table:
                features.append('AI model evaluation & testing')
            elif 'Flow' in table:
                features.append('Workflow automation')
            elif 'Assistant' in table:
                features.append('AI assistant management')
            
            writer.writerow([table, 'Daisy', info['column_count'], purpose, '; '.join(features)])
    
    # 5. Feature Comparison Matrix
    features_file = os.path.join(comparison_dir, '05_feature_comparison.csv')
    with open(features_file, 'w', newline='', encoding='utf-8') as f:
        writer = csv.writer(f)
        writer.writerow(['Feature Category', 'LiteLLM Support', 'Daisy Support', 'LiteLLM Implementation', 'Daisy Implementation'])
        
        feature_matrix = [
            ['User Management', 'Yes', 'Yes', 'LiteLLM_UserTable, LiteLLM_TeamTable', 'User, ApiKey'],
            ['API Key Management', 'Yes', 'Yes', 'LiteLLM_VerificationToken', 'ApiKey'],
            ['Usage Tracking', 'Yes', 'Limited', 'LiteLLM_SpendLogs, Daily*Spend tables', 'Execution'],
            ['Billing & Budgets', 'Yes', 'No', 'LiteLLM_BudgetTable, spend tracking', 'Not present'],
            ['Chat/Messaging', 'No', 'Yes', 'Not present', 'ChatMessage, ChatFlow'],
            ['Document Management', 'Limited', 'Yes', 'LiteLLM_ManagedFileTable', 'DocumentStore, DocumentStoreFileChunk'],
            ['Workflow Management', 'No', 'Yes', 'Not present', 'ChatFlow, Execution, ScheduledTask'],
            ['AI Model Management', 'Yes', 'Yes', 'LiteLLM_ProxyModelTable', 'Assistant, Evaluator'],
            ['Audit Logging', 'Yes', 'Limited', 'LiteLLM_AuditLog', 'UpsertHistory'],
            ['Organization Support', 'Yes', 'No', 'LiteLLM_OrganizationTable', 'Not present'],
            ['Content Filtering', 'Yes', 'No', 'LiteLLM_GuardrailsTable', 'Not present'],
            ['Template System', 'Limited', 'Yes', 'LiteLLM_PromptTable', 'CustomTemplate'],
            ['Evaluation Framework', 'No', 'Yes', 'Not present', 'Evaluation, EvaluationRun, Dataset']
        ]
        
        for feature in feature_matrix:
            writer.writerow(feature)
    
    return comparison_dir

def main():
    """Main function"""
    print("Creating database schema comparison...")
    
    comparison_dir = create_comparison_report()
    
    print(f"\nDatabase comparison complete!")
    print(f"Files saved in '{comparison_dir}/' directory:")
    print("   01_overall_statistics.csv - High-level comparison")
    print("   02_all_tables_comparison.csv - Side-by-side table listing")  
    print("   03_similar_tables.csv - Tables serving similar purposes")
    print("   04_unique_tables.csv - Tables unique to each project")
    print("   05_feature_comparison.csv - Feature support matrix")
    
    print(f"\nQuick Summary:")
    litellm_tables, daisy_tables = load_schema_summaries()
    print(f"   - LiteLLM: {len(litellm_tables)} tables (LLM proxy & usage focus)")
    print(f"   - Daisy: {len(daisy_tables)} entities (workflow & assistant focus)")
    print(f"   - Different architectures serving different purposes")

if __name__ == '__main__':
    main()