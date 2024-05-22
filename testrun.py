# pip install git+https://github.com/lupin-oomura/myopenai.git

import myopenai
import mywhisper
from dotenv import load_dotenv
load_dotenv()



def main():
    mo = myopenai.myopenai()

    #リアルタイム文字起こし
    transcriber = mywhisper.mywhisper(mo, energy=300, pause=0.1, dynamic_energy=False, save_file=False)
    result_queue = transcriber.start_transcribing()

    print("Recording... Press Ctrl+C to stop.")
    try:
        while not transcriber.stop_event.is_set():
            say = result_queue.get()
            print(f"You said: {say}")
            if "処理を終了してください" in say:
                transcriber.stop_event.set()
                transcriber.stop_listening(wait_for_stop=True)
                break
    except KeyboardInterrupt:
        transcriber.stop_event.set()
        transcriber.stop_listening(wait_for_stop=True)
        print("Stopped by user")


if __name__ == "__main__":
    main()




