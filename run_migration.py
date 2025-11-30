import asyncio
import os
import asyncpg

async def run_migration():
    # Get DATABASE_URL from environment
    database_url = os.environ.get('DATABASE_URL')
    if not database_url:
        print("ERROR: DATABASE_URL not set")
        return

    print(f"Connecting to database...")

    # Read SQL file
    with open('create_stripe_tables.sql', 'r') as f:
        sql = f.read()

    # Connect and execute
    try:
        conn = await asyncpg.connect(database_url)
        print("Connected successfully!")

        # Execute the SQL
        await conn.execute(sql)
        print("Migration completed successfully!")

        # Verify tables were created
        tables = await conn.fetch("""
            SELECT table_name
            FROM information_schema.tables
            WHERE table_schema = 'public'
            AND table_name LIKE '%Stripe%'
            ORDER BY table_name
        """)

        print("\nCreated tables:")
        for table in tables:
            print(f"  - {table['table_name']}")

        await conn.close()

    except Exception as e:
        print(f"ERROR: {e}")
        import traceback
        traceback.print_exc()

if __name__ == "__main__":
    asyncio.run(run_migration())
