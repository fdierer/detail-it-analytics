from google.cloud import bigquery
import json
from datetime import datetime, timedelta
import os

# Your project ID
PROJECT_ID = "dilutecalculator-306492c4"

def get_analytics_data():
    """Fetch analytics data from BigQuery"""
    client = bigquery.Client()
    
    # Date calculations
    today = datetime.now().date()
    yesterday = today - timedelta(days=1)
    week_ago = today - timedelta(days=7)
    
    # Format dates for BigQuery
    yesterday_str = yesterday.strftime('%Y%m%d')
    week_ago_str = week_ago.strftime('%Y%m%d')
    
    print(f"📊 Fetching analytics for {yesterday_str}")
    
    # Find analytics dataset
    datasets = list(client.list_datasets())
    analytics_dataset = None
    for dataset in datasets:
        if dataset.dataset_id.startswith('analytics_'):
            analytics_dataset = dataset.dataset_id
            break
            # Override with your specific dataset name
            analytics_dataset = "analytics_492429472"  # Replace XXX with the full number from BigQuery
    
    if not analytics_dataset:
        print("⏳ No analytics dataset found yet. This is normal for the first 24-48 hours.")
        save_empty_metrics()
        return
    
    try:
        # Query 1: Yesterday's Summary (Safe Metrics Only)
        summary_query = f"""
        SELECT 
            COUNT(DISTINCT user_pseudo_id) as daily_users,
            SUM(CASE WHEN event_name = 'dilution_calculator_use' THEN 1 ELSE 0 END) as calculator_uses,
            SUM(CASE WHEN event_name = 'app_store_click' THEN 1 ELSE 0 END) as app_clicks,
            SUM(CASE WHEN event_name = 'page_view' THEN 1 ELSE 0 END) as page_views
        FROM `{PROJECT_ID}.{analytics_dataset}.events_{yesterday_str}`
        """
        
        summary_df = client.query(summary_query).to_dataframe()
        
        # Query 2: Platform Split
        platform_query = f"""
        SELECT 
            CASE 
                WHEN platform = 'WEB' THEN 'Web'
                WHEN platform = 'IOS' THEN 'iOS'
                ELSE platform
            END as platform,
            COUNT(DISTINCT user_pseudo_id) as users
        FROM `{PROJECT_ID}.{analytics_dataset}.events_{yesterday_str}`
        GROUP BY platform
        """
        
        platform_df = client.query(platform_query).to_dataframe()
        
        # Query 3: 7-Day Trend
        trend_query = f"""
        SELECT 
            PARSE_DATE('%Y%m%d', event_date) as date,
            COUNT(DISTINCT user_pseudo_id) as users,
            SUM(CASE WHEN event_name = 'dilution_calculator_use' THEN 1 ELSE 0 END) as calculator_uses
        FROM `{PROJECT_ID}.{analytics_dataset}.events_*`
        WHERE _TABLE_SUFFIX BETWEEN '{week_ago_str}' AND '{yesterday_str}'
        GROUP BY date
        ORDER BY date
        """
        
        trend_df = client.query(trend_query).to_dataframe()
        
        # Query 4: Popular Features (Non-sensitive events only)
        features_query = f"""
        SELECT 
            event_name,
            COUNT(DISTINCT user_pseudo_id) as unique_users
        FROM `{PROJECT_ID}.{analytics_dataset}.events_{yesterday_str}`
        WHERE event_name IN (
            'dilution_calculator_use',
            'app_store_click', 
            'page_view',
            'newsletter_signup',
            'support_form_submit'
        )
        GROUP BY event_name
        ORDER BY unique_users DESC
        """
        
        features_df = client.query(features_query).to_dataframe()
        
        # Calculate safe metrics
        total_users = int(summary_df['daily_users'].iloc[0]) if len(summary_df) > 0 else 0
        calculator_uses = int(summary_df['calculator_uses'].iloc[0]) if len(summary_df) > 0 else 0
        page_views = int(summary_df['page_views'].iloc[0]) if len(summary_df) > 0 else 0
        
        # Calculate conversion rate (safe to show as percentage)
        conversion_rate = (calculator_uses / page_views * 100) if page_views > 0 else 0
        
        # Platform breakdown
        platform_data = {}
        for _, row in platform_df.iterrows():
            platform_data[row['platform']] = int(row['users'])
        
        # Prepare trend data (dates and relative values)
        trend_data = []
        for _, row in trend_df.iterrows():
            trend_data.append({
                'date': row['date'].strftime('%Y-%m-%d'),
                'users': int(row['users']),
                'calculator_uses': int(row['calculator_uses'])
            })
        
        # Feature adoption (show as percentages, not raw numbers)
        feature_adoption = {}
        for _, row in features_df.iterrows():
            if total_users > 0:
                feature_adoption[row['event_name']] = round(row['unique_users'] / total_users * 100, 1)
        
        # Create public-safe metrics
        metrics = {
            'updated': datetime.now().isoformat(),
            'date': yesterday.strftime('%Y-%m-%d'),
            'summary': {
                'daily_active_users': total_users,
                'calculator_conversion_rate': round(conversion_rate, 1),
                'platform_breakdown': platform_data,
                'total_interactions': calculator_uses + int(summary_df['app_clicks'].iloc[0])
            },
            'trend': trend_data,
            'feature_adoption_percentage': feature_adoption,
            'status': 'active'
        }
        
        # Save metrics
        save_metrics(metrics)
        
        print(f"✅ Dashboard updated successfully!")
        print(f"   Users: {total_users}")
        print(f"   Conversion: {conversion_rate:.1f}%")
        
    except Exception as e:
        print(f"❌ Query error: {e}")
        save_empty_metrics()

def save_metrics(metrics):
    """Save metrics to JSON file"""
    os.makedirs('dashboard/data', exist_ok=True)
    with open('dashboard/data/metrics.json', 'w') as f:
        json.dump(metrics, f, indent=2)

def save_empty_metrics():
    """Save empty metrics when no data available"""
    metrics = {
        'updated': datetime.now().isoformat(),
        'date': datetime.now().strftime('%Y-%m-%d'),  # This should give today's date
        'summary': {
            'daily_active_users': 0,
            'calculator_conversion_rate': 0,
            'platform_breakdown': {},
            'total_interactions': 0
        },
        'trend': [],
        'feature_adoption_percentage': {},
        'status': 'waiting_for_data'
    }
    save_metrics(metrics)

if __name__ == "__main__":
    print("🚀 Detail It Analytics Dashboard Generator")
    print(f"⏰ Running at: {datetime.now()}")
    get_analytics_data()
