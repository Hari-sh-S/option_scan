"""
Reorganize parquet files - flatten structure and rename
"""
import os
import shutil
import time

base_dir = 'historical_data/NIFTY'

for expiry in ['WEEK', 'MONTH']:
    expiry_path = os.path.join(base_dir, expiry)
    
    if not os.path.exists(expiry_path):
        continue
    
    for option_type in ['CALL', 'PUT']:
        option_path = os.path.join(expiry_path, option_type)
        suffix = 'CE' if option_type == 'CALL' else 'PE'
        
        if not os.path.exists(option_path):
            continue
            
        # Get all strike folders
        strike_folders = [f for f in os.listdir(option_path) if os.path.isdir(os.path.join(option_path, f))]
        
        for strike_folder in strike_folders:
            strike_path = os.path.join(option_path, strike_folder)
            
            # Convert folder name back to strike name
            strike_name = strike_folder.replace('plus', '+').replace('minus', '-')
            
            # Find parquet file in this folder
            for f in os.listdir(strike_path):
                if f.endswith('.parquet'):
                    old_path = os.path.join(strike_path, f)
                    new_name = f'{strike_name}_{suffix}.parquet'
                    new_path = os.path.join(expiry_path, new_name)
                    
                    # Copy instead of move to avoid permission issues
                    shutil.copy2(old_path, new_path)
                    print(f'Created: {new_name}')
        
        # After copying all files, remove the CALL/PUT folder
        time.sleep(1)  # Allow file handles to close
        try:
            shutil.rmtree(option_path)
            print(f'Removed folder: {option_type}')
        except Exception as e:
            print(f'Could not remove {option_type} folder: {e}')

print('\nDone! Files reorganized.')
