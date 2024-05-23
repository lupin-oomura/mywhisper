# pip install git+https://github.com/lupin-oomura/myopenai.git

import myopenai
from mywhisper import mywhisper
from dotenv import load_dotenv
load_dotenv()
import queue


def main():
    mo = myopenai.myopenai()

    #リアルタイム文字起こし
    transcriber = mywhisper(mo, energy=300, pause=0.1, silence_duration=5, dynamic_energy=False, save_file=False)
    result_queue = transcriber.start_stt()

    print("Recording... Press Ctrl+C to stop.")
    txt_all = ""
    try:
        while not transcriber.stop_event.is_set():
            try:
                say = result_queue.get(timeout=0.5)
                print(f"You said: {say}")
                txt_all += say

                if "処理を終了してください" in say:
                    print("stopped by talk command")
                    break

                if transcriber.stop_event.is_set() :
                    print("stopped by silence")
            except queue.Empty:
                continue

    except KeyboardInterrupt:
        print("keyboard interrupt")

    transcriber.stop_stt()


    #キューの残り物を抽出
    try:
        say = result_queue.get(timeout=0.5)
        print(f"You said: {say}")
        txt_all += say
    except queue.Empty:
        pass # キューが空の場合は何もしない

    #メモリクリーンアップ
    transcriber.cleanup()
    print("Stopped by user")

    print(f"predicted txt = {txt_all}")

    
if __name__ == "__main__":
    main()




