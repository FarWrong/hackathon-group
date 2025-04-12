import os
import threading
from queue import Queue

# Create a queue for percentage values
percentage_queue = Queue()

# Worker thread function that writes percentages to file
def percentage_writer():
    while True:
        # get percentage from queue (blocks until item available)
        percentage = percentage_queue.get()
        
        if percentage is None:
            break
            
        # write to file one up the dir
        filepath = os.path.join('..', 'percentage.txt')
        try:
            with open(filepath, 'w') as f:
                f.write(f"{percentage:.1f}")
        except Exception as e:
            print(f"Error writing to file: {e}")
            
        # done
        percentage_queue.task_done()

# Start worker thread
writer_thread = threading.Thread(target=percentage_writer, daemon=True)
writer_thread.start()
