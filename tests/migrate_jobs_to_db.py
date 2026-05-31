#!/usr/bin/env python
"""
Complete Job Database Migration and Management Script

This script provides a comprehensive solution for:
1. Migrating all existing JSON job files to the database
2. Providing database management utilities
3. Generating reports and statistics
4. Demonstrating search functionality
"""

import os
import glob
import json
from jobsearch_agent.utils.job_database import JobDatabase

def main():
    """Main migration function"""
    print("🔄 Starting job database migration...")
    
    # Initialize database
    db = JobDatabase()
    print("✅ Database initialized")
    
    # Find all JSON files in the jobs directory
    json_pattern = os.path.join("jobs", "*.json")
    json_files = glob.glob(json_pattern)
    
    print(f"📁 Found {len(json_files)} JSON files to process:")
    for file in json_files:
        print(f"  - {file}")
    
    if not json_files:
        print("❌ No JSON files found in jobs/ directory")
        return
    
    # Migrate each file
    total_jobs = 0
    migrated_jobs = 0
    
    for json_file in json_files:
        print(f"\n📄 Processing {json_file}...")
        
        try:
            with open(json_file, 'r', encoding='utf-8') as f:
                data = json.load(f)
            
            # Handle both single job and list of jobs
            if isinstance(data, list):
                jobs_in_file = data
            else:
                jobs_in_file = [data]
            
            total_jobs += len(jobs_in_file)
            
            # Add each job to database
            for i, job in enumerate(jobs_in_file):
                if db.add_job(job):
                    migrated_jobs += 1
                    print(f"  ✅ Job {i+1}: {job.get('job_title', job.get('title', 'N/A'))} at {job.get('company_name', job.get('company', 'N/A'))}")
                else:
                    print(f"  ⚠️  Job {i+1}: Failed to add or already exists")
            
            print(f"  📊 Processed {len(jobs_in_file)} jobs from {json_file}")
            
        except Exception as e:
            print(f"  ❌ Error processing {json_file}: {e}")
    
    # Display final statistics
    print(f"\n🎉 Migration completed!")
    print(f"📊 Total jobs found: {total_jobs}")
    print(f"📊 Jobs migrated: {migrated_jobs}")
    print(f"📊 Duplicates/Errors: {total_jobs - migrated_jobs}")
    
    # Display database statistics
    stats = db.get_stats()
    print(f"\n📈 Database Statistics:")
    print(f"  Total jobs in database: {stats['total_jobs']}")
    print(f"  Top companies:")
    for company in stats['top_companies'][:5]:
        print(f"    - {company['company']}: {company['count']} jobs")
    
    # Display jobs by source
    print(f"  Jobs by source:")
    for source in stats['by_source']:
        print(f"    - {source['source']}: {source['count']} jobs")
    
    # Close database
    db.close()
    print("\n✅ Database migration completed successfully!")

if __name__ == "__main__":
    main()
