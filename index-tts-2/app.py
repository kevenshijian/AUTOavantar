import os
import sys
import threading
from cy_app import *
import threading
current_dir = os.path.dirname(os.path.abspath(__file__))
sys.path.append(current_dir)

if __name__ == "__main__":


    fastapi_thread = threading.Thread(target=start_service)
    gradio_thread = threading.Thread(target=start_gradio)
    word_thread = threading.Thread(target=start_workers, args=(1,))

    fastapi_thread.start()
    gradio_thread.start()
    word_thread.start()

    fastapi_thread.join()
    gradio_thread.join()
    word_thread.join()