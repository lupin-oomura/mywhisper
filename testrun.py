# pip install git+https://github.com/lupin-oomura/myopenai.git

import myopenai
from mywhisper import mywhisper
from dotenv import load_dotenv
load_dotenv()



def main():
    mo = myopenai.myopenai()

    #リアルタイム文字起こし
    transcriber = mywhisper(mo, energy=300, pause=0.1, silence_duration=5, dynamic_energy=False, save_file=False)
    result_queue = transcriber.start_transcribing()

    print("Recording... Press Ctrl+C to stop.")
    try:
        while not transcriber.stop_event.is_set():
            say = result_queue.get()
            print(f"You said: {say}")
            if "処理を終了してください" in say:
                transcriber.stop()
                break

            if transcriber.stop_event.is_set() :
                print("stopped by silence")


    except KeyboardInterrupt:
        transcriber.stop()
        print("Stopped by user")


if __name__ == "__main__":
    main()




