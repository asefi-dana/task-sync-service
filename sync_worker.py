import os
import sys
import asyncio
import time
from telethon import TelegramClient
from telethon.sessions import StringSession
from telethon.errors import FloodWaitError, RpcCallFailError

api_id = int(os.environ['TG_API_ID'])
api_hash = os.environ['TG_API_HASH']
session_str = os.environ['TG_STRING_SESSION']
series_choice = os.environ.get('SERIES_NAME', 'Cukurova')
target_channel_id = os.environ.get('TARGET_CHANNEL', 'rozgarani')
batch_limit = int(os.environ.get('BATCH_LIMIT', '2'))

# Robust download with retry mechanism
async def download_file_with_retry(client, msg, local_path, max_retries=5):
    for attempt in range(1, max_retries + 1):
        try:
            print(f"Downloading attempt {attempt}/{max_retries}...")
            # Use iter_download with 512KB chunks for stability on Telegram DC
            total_size = msg.file.size
            downloaded = 0
            with open(local_path, 'wb') as f:
                async for chunk in client.iter_download(msg.media, request_size=512*1024):
                    f.write(chunk)
                    downloaded += len(chunk)
                    if downloaded % (50 * 1024 * 1024) < len(chunk):
                        percent = (downloaded / total_size) * 100
                        print(f"  Downloaded {downloaded/(1024*1024):.1f}MB / {total_size/(1024*1024):.1f}MB ({percent:.1f}%)", flush=True)
            print("Download completed successfully!", flush=True)
            return True
        except Exception as e:
            print(f"Error during download attempt {attempt}: {e}", flush=True)
            if attempt < max_retries:
                sleep_time = attempt * 10
                print(f"Retrying in {sleep_time}s...", flush=True)
                await asyncio.sleep(sleep_time)
            else:
                raise e
    return False

# Robust upload with retry mechanism
async def upload_file_with_retry(client, target, local_path, caption, max_retries=3):
    for attempt in range(1, max_retries + 1):
        try:
            print(f"Uploading attempt {attempt}/{max_retries}...")
            await client.send_file(
                target,
                local_path,
                caption=caption,
                supports_streaming=True
            )
            print("Upload completed successfully!", flush=True)
            return True
        except FloodWaitError as e:
            print(f"FloodWait: sleeping {e.seconds}s...")
            await asyncio.sleep(e.seconds + 2)
        except Exception as e:
            print(f"Error during upload attempt {attempt}: {e}")
            if attempt < max_retries:
                await asyncio.sleep(15)
            else:
                raise e
    return False

async def main():
    print(f"Starting Robust Sync Engine for: {series_choice} -> {target_channel_id}")
    client = TelegramClient(
        StringSession(session_str),
        api_id,
        api_hash,
        timeout=120,
        request_retries=15,
        connection_retries=None,
        retry_delay=5
    )
    await client.start()
    
    source = await client.get_entity('gem_series_I')
    try:
        target = await client.get_entity(target_channel_id)
    except Exception:
        target = await client.get_entity(int(target_channel_id))
        
    print(f"Connected: Source='{source.title}' | Target='{target.title}'")
    
    # 1. Find candidate episodes based on choice
    candidates = []
    search_term = "Cukurova" if "cukurova" in series_choice.lower() else "Deha"
    print(f"Searching source channel for '{search_term}'...")
    
    async for msg in client.iter_messages(source, search=search_term, limit=300):
        if msg.file and (getattr(msg.file, 'duration', 0) or 0) >= 4500: # >= 75 min
            candidates.append(msg)
            
    candidates.sort(key=lambda m: m.id)
    print(f"Found {len(candidates)} candidate long episodes in source.")
    
    # 2. Check already uploaded files in target channel
    existing_files = set()
    async for t_msg in client.iter_messages(target, limit=200):
        if t_msg.file and t_msg.file.name:
            existing_files.add(t_msg.file.name)
            
    to_process = [m for m in candidates if (m.file and m.file.name and m.file.name not in existing_files)]
    print(f"Episodes already uploaded: {len(existing_files)}. Remaining: {len(to_process)}")
    
    # 3. Process the next batch
    for msg in to_process[:batch_limit]:
        fn = msg.file.name or f"episode_{msg.id}.mkv"
        sz_mb = msg.file.size / (1024*1024)
        dur_min = (getattr(msg.file, 'duration', 0) or 0) / 60
        print(f"\n=======================================================")
        print(f"Processing: {fn} ({sz_mb:.1f} MB, {dur_min:.1f} min)")
        print(f"=======================================================")
        
        local_path = f"/tmp/{fn}"
        await download_file_with_retry(client, msg, local_path)
        
        caption = msg.message or f"🎬 {fn}"
        await upload_file_with_retry(client, target, local_path, caption)
        
        if os.path.exists(local_path):
            os.remove(local_path)
            print("Cleaned local runner storage.")
            
        print("Waiting 10s cooldown before next file...")
        await asyncio.sleep(10)
        
    print("\nAll requested episodes in this batch synced successfully!")
    await client.disconnect()

if __name__ == '__main__':
    asyncio.run(main())
