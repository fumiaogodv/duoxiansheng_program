import pysrt
def sub_srt():
    subs=pysrt.open("one.srt")
    srt_num=len(subs)
    for i in subs :
        if i.text.strip():
            # 分割文本为单词
            words = i.text.strip().split()
            # 获取第一个单词
            first_word = words[0]
            print(f"num is {i.index} content is {first_word}")


sub_srt()