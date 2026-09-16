import os
import sys
import asyncio
import math
from telethon import TelegramClient, utils
from telethon.sessions import StringSession
from telethon.tl.functions.upload import GetFileRequest

api_id = int(os.environ['TG_API_ID'])
api_hash = os.environ['TG_API_HASH']
session_str = os.environ['TG_STRING_SESSION']
series_choice = os.environ.get('SERIES_NAME', 'Cukurova')
target_channel_id = os.environ.get('TARGET_CHANNEL', 'rozgarani')
batch_limit = int(os.environ.get('BATCH_LIMIT', '2'))

# Multi-Stream Parallel Turbo Downloader
async def download_turbo(client, document, out_file, max_workers=8):
    dc_id, location = utils.get_input_location(document)
    file_size = document.size
    chunk_size = 512 * 1024 # 512 KB (exact power of 2 and multiple of 4096)
    total_parts = math.ceil(file_size / chunk_size)
    print(f"🚀 Multi-Connection Turbo Download: {file_size/(1024*1024):.1f}MB ({total_parts} chunks) with {max_workers} parallel workers...")
    
    queue = asyncio.Queue()
    for part in range(total_parts):
        queue.put_nowait(part)
        
    f = open(out_file, 'wb+')
    f.truncate(file_size)
    
    downloaded = 0
    lock = asyncio.Lock()
    
    async def worker():
        nonlocal downloaded
        while not queue.empty():
            part = await queue.get()
            offset = part * chunk_size
            # Telegram requires limit to be divisible by 4096/power of 2. Always pass chunk_size!
            limit = chunk_size
            
            for retry in range(5):
                try:
                    result = await client(GetFileRequest(
                        location=location,
                        offset=offset,
                        limit=limit
                    ))
                    f.seek(offset)
                    f.write(result.bytes)
                    async with lock:
                        downloaded += len(result.bytes)
                        if downloaded % (50 * 1024 * 1024) < len(result.bytes):
                            pct = min(100.0, (downloaded / file_size) * 100)
                            print(f"  [Download Progress] {downloaded/(1024*1024):.1f}MB / {file_size/(1024*1024):.1f}MB ({pct:.1f}%)", flush=True)
                    break
                except Exception as e:
                    if retry == 4:
                        raise e
                    await asyncio.sleep(1 + retry)
            queue.task_done()

    workers = [asyncio.create_task(worker()) for _ in range(max_workers)]
    await asyncio.gather(*workers)
    f.close()
    print("✅ Turbo Download Complete!", flush=True)

async def main():
    print(f"=== Multi-Stream Turbo Engine Started for {series_choice} -> {target_channel_id} ===")
    client = TelegramClient(
        StringSession(session_str),
        api_id,
        api_hash,
        timeout=120,
        request_retries=15,
        connection_retries=None
    )
    await client.start()
    
    source = await client.get_entity('gem_series_I')
    try:
        target = await client.get_entity(target_channel_id)
    except Exception:
        target = await client.get_entity(int(target_channel_id))
        
    print(f"Source: {source.title} | Target: {target.title}")
    
    search_term = "Cukurova" if "cukurova" in series_choice.lower() else "Deha"
    candidates = []
    async for msg in client.iter_messages(source, search=search_term, limit=300):
        if msg.file and (getattr(msg.file, 'duration', 0) or 0) >= 4500:
            candidates.append(msg)
            
    candidates.sort(key=lambda m: m.id)
    
    existing_files = set()
    async for t_msg in client.iter_messages(target, limit=200):
        if t_msg.file and t_msg.file.name:
            existing_files.add(t_msg.file.name)
            
    to_process = [m for m in candidates if (m.file and m.file.name and m.file.name not in existing_files)]
    print(f"Target already has: {len(existing_files)} files. Remaining: {len(to_process)}")
    
    for msg in to_process[:batch_limit]:
        fn = msg.file.name or f"episode_{msg.id}.mkv"
        sz_mb = msg.file.size / (1024*1024)
        dur_min = (getattr(msg.file, 'duration', 0) or 0) / 60
        print(f"\n=======================================================", flush=True)
        print(f"Processing: {fn} ({sz_mb:.1f} MB, {dur_min:.1f} min)", flush=True)
        print(f"=======================================================", flush=True)
        
        local_path = f"/tmp/{fn}"
        
        # Robust parallel download
        await download_turbo(client, msg.document, local_path, max_workers=8)
        
        # Upload
        caption = msg.message or f"🎬 {fn}"
        print("Uploading file to target channel...", flush=True)
        await client.send_file(
            target,
            local_path,
            caption=caption,
            supports_streaming=True
        )
        print(f"✅ Uploaded successfully to {target.title}!", flush=True)
        
        if os.path.exists(local_path):
            os.remove(local_path)
            
        await asyncio.sleep(5)
        
    print("Turbo batch finished successfully!")
    await client.disconnect()

if __name__ == '__main__':
    asyncio.run(main())
