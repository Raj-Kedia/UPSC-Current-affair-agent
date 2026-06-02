import os
import urllib.request
import json

def download_pyqs():
    data_dir = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), 'data')
    os.makedirs(data_dir, exist_ok=True)
    
    target_file = os.path.join(data_dir, 'upsc_mains_pyqs.json')
    url = "https://raw.githubusercontent.com/amanbh2/UPSC-Star/master/UPSC%20Star%20Data.json"
    
    print(f"Downloading UPSC Mains PYQ dataset from: {url}")
    try:
        req = urllib.request.Request(
            url, 
            headers={'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64)'}
        )
        with urllib.request.urlopen(req) as response:
            data = json.loads(response.read().decode('utf-8'))
            
            # Print stats
            total_qs = sum(len(qs) for qs in data.values())
            print(f"Successfully downloaded {total_qs} questions across papers: {list(data.keys())}")
            
            # Write to file
            with open(target_file, 'w', encoding='utf-8') as f:
                json.dump(data, f, indent=2, ensure_ascii=False)
            print(f"Saved UPSC Mains PYQ data to: {target_file}")
            return True
    except Exception as e:
        print(f"Error downloading PYQ data: {e}")
        return False

if __name__ == '__main__':
    download_pyqs()
