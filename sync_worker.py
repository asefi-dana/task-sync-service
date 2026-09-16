import os
import asyncio
from telethon import TelegramClient
from telethon.sessions import StringSession

api_id = int(os.environ['TG_API_ID'])
api_hash = os.environ['TG_API_HASH']
session_str = os.environ['TG_STRING_SESSION']
series_pattern = os.environ.get('SERIES_NAME', 'Cukurova')
target_channel_id = os.environ.get('TARGET_CHANNEL', 'rozgarani')
batch_limit = int(os.environ.get('BATCH_LIMIT', '3'))

async def main():
    print(f"Connecting client for series: {series_pattern} -> {target_channel_id} (limit: {batch_limit})...")
    client = TelegramClient(StringSession(session_str), api_id, api_hash)
    await client.start()
    
    source = await client.get_entity('gem_series_I')
    try:
        target = await client.get_entity(target_channel_id)
    except Exception:
        target = await client.get_entity(int(target_channel_id))
        
    print(f"Source: {source.title} | Target: {target.title}")
    
    candidates = []
    async for msg in client.iter_messages(source, search=series_pattern, limit=200):
        if msg.file and (getattr(msg.file, 'duration', 0) or 0) >= 4500:
            candidates.append(msg)
            
    candidates.sort(key=lambda m: m.id)
    print(f"Found {len(candidates)} candidate long episodes in source.")
    
    existing_files = set()
    async for t_msg in client.iter_messages(target, limit=100):
        if t_msg.file and t_msg.file.name:
            existing_files.add(t_msg.file.name)
            
    to_process = [m for m in candidates if (m.file and m.file.name and m.file.name not in existing_files)]
    print(f"Remaining to upload: {len(to_process)} episodes. Processing next {min(batch_limit, len(to_process))}...")
    
    for msg in to_process[:batch_limit]:
        fn = msg.file.name or f"episode_{msg.id}.mkv"
        sz_gb = msg.file.size / (1024*1024*1024)
        print(f"\n--- Downloading: {fn} ({sz_gb:.2f} GB) ---")
        
        local_path = f"/tmp/{fn}"
        await client.download_media(msg, file=local_path)
        print(f"Downloaded to {local_path}. Uploading to target...")
        
        caption = msg.message or f"🎬 {fn}"
        await client.send_file(
            target,
            local_path,
            caption=caption,
            supports_streaming=True
        )
        print(f"Uploaded successfully to {target.title}!")
        
        if os.path.exists(local_path):
            os.remove(local_path)
            print("Local runner file cleaned up.")
            
        await asyncio.sleep(5)
        
    print("\nBatch finished cleanly!")
    await client.disconnect()

if __name__ == '__main__':
    asyncio.run(main())
