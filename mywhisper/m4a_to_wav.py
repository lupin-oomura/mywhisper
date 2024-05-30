from pydub import AudioSegment

def convert_m4a_to_wav(input_file, output_file):
    # m4aファイルを読み込み
    audio = AudioSegment.from_file(input_file, format="m4a")
    
    # wavファイルとして書き出し
    audio.export(output_file, format="wav")
    
    print(f"Converted {input_file} to {output_file}")

# 変換するファイルのパスを指定
input_file = "testdata.m4a"
output_file = "testdata.wav"

# 変換を実行
convert_m4a_to_wav(input_file, output_file)