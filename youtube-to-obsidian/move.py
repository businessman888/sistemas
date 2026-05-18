import os
import shutil

os.makedirs('app/modules/youtube', exist_ok=True)
os.makedirs('app/core', exist_ok=True)

try:
    shutil.move('app/routes/videos.py', 'app/modules/youtube/routes.py')
except Exception as e: print(e)
try:
    shutil.move('app/services/youtube.py', 'app/modules/youtube/youtube.py')
except Exception as e: print(e)
try:
    shutil.move('app/services/transcript.py', 'app/modules/youtube/transcript.py')
except Exception as e: print(e)
try:
    shutil.move('app/services/obsidian.py', 'app/modules/youtube/obsidian.py')
except Exception as e: print(e)
try:
    shutil.move('app/config.py', 'app/core/config.py')
except Exception as e: print(e)
try:
    shutil.move('app/utils', 'app/core/utils')
except Exception as e: print(e)
try:
    shutil.rmtree('app/routes')
except Exception as e: print(e)
try:
    shutil.rmtree('app/services')
except Exception as e: print(e)

print("done")
