import re
import os
import time
import requests
import json

# --- SiliconFlow API 配置 ---
# !!! 请确认这是你从 SiliconFlow 官网获得的真实 API Key !!!
# 如果这是你的真实密钥，当前的程序逻辑将不再错误地阻止其使用。
SILIFLOW_API_TOKEN = "sk-dbnapyptglaxkkkivbbbibcyflferyvjnxdrruccwdyjlzhh"
SILIFLOW_CHAT_ENDPOINT = "https://api.siliconflow.cn/v1/chat/completions"
SILIFLOW_MODEL_NAME = "tencent/Hunyuan-MT-7B"

# --- SiliconFlow 翻译提示词 (Prompt Engineering) ---
SILIFLOW_TRANSLATION_PROMPT = """
你是一名专业的电子竞技（CS游戏）字幕翻译员。请将以下英文 CS 游戏字幕文本翻译成简洁、流畅、自然的中文。

翻译要求：
1.  **核心目标**：将英文CS游戏字幕准确、自然地翻译成中文。
2.  **简洁口语化**：译文应符合中文观众的表达习惯，简洁明了，贴近口语，避免生硬直译。
3.  **最终输出**：只返回翻译后的中文文本，不要包含任何英文原文、编号、额外说明或对话。

请翻译以下英文文本：
{english_text}
"""

# 3.  **人名和队名处理**：
#     *   **以下人名（选手ID）和队名请严格保留英文原文，不要进行任何翻译、音译或改写：**
#         G2: MATYS, SunPayus, malbsMd, HeavyGod, huNter-
#         Lynn Vision: Starry, EmiliaQAQ, C4LLM3SU3, z4kr, Westmelon
#         FURIA: molodoy,yuurih,FalleN,KSCERATO,YEKINDAR
#         Liquid: NAF,ultimate,Twistzz,NertZ,siuhy
#         *TYLOO： "Jee, Mercury, JamYoung, Moseyuh, Attacker"
#         *GamerLegion： "REZ, PR, Tauson, ztr, Kursy"
#         *The MongolZ： "910, mzinho, bLitz, Senzu, Techno"
#         *3DMAX： "bodvy, Ex3rcice, Graviti, Maka, Lucky"
#         *Falcons： "NiKo, m0NESY, TeSeS, kyousuke, kyxsan"
#         *Virtus.pro： "t00RO, ICY, fame, FL1T, Perfecto"
#         *Aurora： "jottAAA, Maj3R, XANTARES, Wicadia, woxic"
#         *Astralis： "Magisk, HooXi, Staehr, device, jabbi"
#     *   对于未在上述列表中，但明显是选手ID或队名的词汇，请在保留英文的前提下，谨慎判断是否需要音译或意译。




# --- 辅助函数 (保持不变) ---
def parse_srt_block(block_str):
    block_str = block_str.lstrip('\ufeff')
    lines = block_str.strip().split('\n')
    if len(lines) < 3:
        if len(lines) >= 2 and re.match(r'^\d+$', lines[0]) and '-->' in lines[1]:
            try:
                block_id = int(lines[0])
                time_str = lines[1]
                start_time_str, end_time_str = time_str.split(' --> ')
                return block_id, start_time_str, end_time_str, []
            except (ValueError, IndexError):
                pass
        print(f"警告: 无法解析字幕块: '{lines[0] if lines else '空块'}', 文本太短或格式不正确. 跳过此块.")
        return None

    try:
        block_id = int(lines[0])
        time_str = lines[1]
        text_lines = [line.strip() for line in lines[2:] if line.strip()]

        start_time_str, end_time_str = time_str.split(' --> ')
        return block_id, start_time_str, end_time_str, text_lines
    except (ValueError, IndexError) as e:
        print(f"警告: 无法解析字幕块: '{lines[0] if lines else '空块'}', 原因: {e}. 跳过此块.")
        return None


def srt_time_to_seconds(time_str):
    h, m, s_ms = time_str.split(':')
    s, ms = s_ms.split(',')
    total_seconds = int(h) * 3600 + int(m) * 60 + int(s) + int(ms) / 1000
    return total_seconds


def seconds_to_srt_time(total_seconds):
    hours = int(total_seconds // 3600)
    total_seconds %= 3600
    minutes = int(total_seconds // 60)
    total_seconds %= 60
    seconds = int(total_seconds)
    milliseconds = int((total_seconds - seconds) * 1000)
    return f"{hours:02d}:{minutes:02d}:{seconds:02d},{milliseconds:03d}"


def merge_srt_sentences_optimized(srt_content, max_chars_per_segment=100, max_duration_sec_per_segment=7):
    blocks = srt_content.strip().split('\n\n')
    parsed_blocks = [parse_srt_block(block) for block in blocks if block.strip()]
    parsed_blocks = [block for block in parsed_blocks if block is not None and block[3]]

    merged_data = []
    current_segment_blocks = []
    block_id_counter = 1

    sentence_end_pattern = re.compile(r'[.?!](["\'》）\]\}]*) ?$')

    def _flush_current_segment():
        nonlocal current_segment_blocks, block_id_counter
        if not current_segment_blocks:
            return

        first_block_in_segment = current_segment_blocks[0]
        last_block_in_segment = current_segment_blocks[-1]

        combined_text = ' '.join([' '.join(b[3]).strip() for b in current_segment_blocks]).strip()
        combined_text = re.sub(r'\s+', ' ', combined_text).strip()

        if combined_text:
            merged_data.append({
                'id': block_id_counter,
                'start': first_block_in_segment[1],
                'end': last_block_in_segment[2],
                'text': combined_text
            })
            block_id_counter += 1
        current_segment_blocks = []

    for i, block_info in enumerate(parsed_blocks):
        original_block_id, original_start_time_str, original_end_time_str, text_lines = block_info
        block_full_text = ' '.join(text_lines).strip()

        if not block_full_text:
            continue

        tentative_text_parts = [' '.join(b[3]).strip() for b in current_segment_blocks]
        tentative_text_parts.append(block_full_text)
        tentative_combined_text = ' '.join(tentative_text_parts).strip()
        tentative_combined_text = re.sub(r'\s+', ' ', tentative_combined_text).strip()

        segment_start_time_str = current_segment_blocks[0][1] if current_segment_blocks else original_start_time_str
        tentative_start_time_sec = srt_time_to_seconds(segment_start_time_str)
        tentative_end_time_sec = srt_time_to_seconds(original_end_time_str)
        tentative_duration = tentative_end_time_sec - tentative_start_time_sec

        is_current_segment_too_long = (
                len(tentative_combined_text) > max_chars_per_segment or
                tentative_duration > max_duration_sec_per_segment
        )
        is_current_block_ends_sentence = sentence_end_pattern.search(block_full_text)

        should_cut = False
        if is_current_segment_too_long and current_segment_blocks:
            should_cut = True

        if is_current_block_ends_sentence and len(current_segment_blocks) > 0:
            should_cut = True

        if should_cut and current_segment_blocks:
            _flush_current_segment()
            current_segment_blocks.append(block_info)
        else:
            current_segment_blocks.append(block_info)

    _flush_current_segment()

    return merged_data


def generate_new_srt(merged_data, bilingual_format='two_lines'):
    output_lines = []
    for item in merged_data:
        output_lines.append(str(item['id']))
        output_lines.append(f"{item['start']} --> {item['end']}")

        original_text = item['text']
        translated_text = item.get('translated_text', '').strip()

        if translated_text:
            if bilingual_format == 'two_lines':
                output_lines.append(original_text)
                output_lines.append(translated_text)
            elif bilingual_format == 'one_line_slash':
                output_lines.append(f"{original_text} / {translated_text}")
            elif bilingual_format == 'one_line_pipe':
                output_lines.append(f"{original_text} | {translated_text}")
            elif bilingual_format == 'only_english':
                output_lines.append(original_text)
            elif bilingual_format == 'only_chinese':
                output_lines.append(translated_text)
            else:
                output_lines.append(original_text)
                output_lines.append(translated_text)
        else:
            output_lines.append(original_text)

        output_lines.append('')
    return '\n'.join(output_lines)


# --- SiliconFlow 翻译功能 ---
def translate_texts_with_siliflow_batched(texts_to_translate, batch_size=1):
    """
    使用 SiliconFlow Chat Completions API 翻译文本列表。
    """
    # 修正后的 API Token 检查逻辑
    if not SILIFLOW_API_TOKEN or not SILIFLOW_API_TOKEN.strip():
        print("\n❌ 错误: SiliconFlow API Token 未设置或为空。请确保已提供有效的 Bearer Token。")
        return [f"ERROR_TOKEN_MISSING" for _ in texts_to_translate]

    print(f"\n配置 SiliconFlow API，使用模型: {SILIFLOW_MODEL_NAME}")
    print(f"使用的 API 端点: {SILIFLOW_CHAT_ENDPOINT}")

    headers = {
        "Content-Type": "application/json",
        "Authorization": f"Bearer {SILIFLOW_API_TOKEN}"
    }

    all_translated_texts = []
    total_texts = len(texts_to_translate)
    max_retries = 3
    retry_delay_seconds = 10
    request_timeout_seconds = 90

    print(f"预计翻译 {total_texts} 段字幕。")

    for i in range(0, total_texts, batch_size):
        current_batch_translations = []

        for j in range(batch_size):
            global_idx_of_text = i + j
            if global_idx_of_text >= total_texts:
                break

            text = texts_to_translate[global_idx_of_text]

            if not text or not text.strip():
                print(f"段落 {global_idx_of_text + 1}/{total_texts}: 原始文本为空，跳过翻译。")
                current_batch_translations.append("")
                continue

            retries = 0
            translated_segment = ""
            full_prompt = SILIFLOW_TRANSLATION_PROMPT.format(english_text=text)

            print(
                f"正在翻译段落 {global_idx_of_text + 1}/{total_texts}: "
                f"原文 (前50字): '{text[:min(len(text), 50)]}{'...' if len(text) > 50 else ''}'"
            )

            while retries < max_retries:
                try:
                    payload = {
                        "model": SILIFLOW_MODEL_NAME,
                        "messages": [
                            {
                                "role": "user",
                                "content": full_prompt
                            }
                        ]
                    }

                    response = requests.post(
                        SILIFLOW_CHAT_ENDPOINT,
                        headers=headers,
                        json=payload,
                        timeout=request_timeout_seconds
                    )
                    response.raise_for_status()

                    response_json = response.json()

                    if response_json and "choices" in response_json and len(response_json["choices"]) > 0:
                        first_choice = response_json["choices"][0]
                        if "message" in first_choice and "content" in first_choice["message"]:
                            translated_segment = first_choice["message"]["content"].strip()
                            print(
                                f"  翻译成功。译文 (前50字): '{translated_segment[:min(len(translated_segment), 50)]}{'...' if len(translated_segment) > 50 else ''}'"
                            )
                        else:
                            print(
                                f"警告: 无法从 SiliconFlow 响应中提取消息内容 (段落 {global_idx_of_text + 1}). "
                                f"响应结构可能不符合预期。原始响应: {json.dumps(response_json, ensure_ascii=False, indent=2)}")
                            translated_segment = "ERROR_SILIFLOW_PARSE_FAILED"
                    else:
                        print(f"警告: SiliconFlow 翻译失败 (段落 {global_idx_of_text + 1}): "
                              f"没有 'choices' 或 'choices' 为空。响应: {json.dumps(response_json, ensure_ascii=False, indent=2)}")
                        translated_segment = "ERROR_SILIFLOW_NO_CHOICES"
                    break

                except requests.exceptions.HTTPError as e:
                    retries += 1
                    status_code = e.response.status_code if e.response is not None else 'N/A'
                    response_text = e.response.text if e.response is not None else 'No response text'
                    error_message = f"SiliconFlow API 请求失败 (HTTP {status_code} - 段落 {global_idx_of_text + 1}): {response_text}"
                    if retries < max_retries:
                        print(f"{error_message}. 正在重试 {retries}/{max_retries}...")
                        print(f"等待 {retry_delay_seconds} 秒后重试...")
                        time.sleep(retry_delay_seconds)
                    else:
                        print(f"{error_message}. 达到最大重试次数。")
                        translated_segment = f"ERROR_SILIFLOW_HTTP_{status_code}"
                        break
                except requests.exceptions.ConnectionError as e:
                    retries += 1
                    error_message = f"SiliconFlow API 请求失败 (网络连接错误 - 段落 {global_idx_of_text + 1}): {e}"
                    if retries < max_retries:
                        print(f"{error_message}. 正在重试 {retries}/{max_retries}...")
                        print(f"等待 {retry_delay_seconds} 秒后重试...")
                        time.sleep(retry_delay_seconds)
                    else:
                        print(f"{error_message}. 达到最大重试次数。")
                        translated_segment = "ERROR_SILIFLOW_CONNECTION"
                        break
                except requests.exceptions.Timeout:
                    retries += 1
                    error_message = f"SiliconFlow API 请求失败 (超时 - 段落 {global_idx_of_text + 1}): 请求在规定时间内未完成 ({request_timeout_seconds}秒)。"
                    if retries < max_retries:
                        print(f"{error_message}. 正在重试 {retries}/{max_retries}...")
                        print(f"等待 {retry_delay_seconds} 秒后重试...")
                        time.sleep(retry_delay_seconds)
                    else:
                        print(f"{error_message}. 达到最大重试次数。")
                        translated_segment = "ERROR_SILIFLOW_TIMEOUT"
                        break
                except json.JSONDecodeError as e:
                    retries += 1
                    try:
                        raw_response_text = response.text
                    except NameError:
                        raw_response_text = "Response object not available."
                    error_message = f"SiliconFlow API 响应解析失败 (非JSON格式 - 段落 {global_idx_of_text + 1}): {e}. 原始响应: {raw_response_text}"
                    if retries < max_retries:
                        print(f"{error_message}. 正在重试 {retries}/{max_retries}...")
                        print(f"等待 {retry_delay_seconds} 秒后重试...")
                        time.sleep(retry_delay_seconds)
                    else:
                        print(f"{error_message}. 达到最大重试次数。")
                        translated_segment = "ERROR_SILIFLOW_INVALID_JSON"
                        break
                except Exception as e:
                    retries += 1
                    error_message = f"SiliconFlow API 请求发生未知错误 (段落 {global_idx_of_text + 1}): {type(e).__name__}: {e}"
                    if retries < max_retries:
                        print(f"{error_message}. 正在重试 {retries}/{max_retries}...")
                        print(f"等待 {retry_delay_seconds} 秒后重试...")
                        time.sleep(retry_delay_seconds)
                    else:
                        print(f"{error_message}. 达到最大重试次数。")
                        translated_segment = "ERROR_SILIFLOW_UNKNOWN"
                        break

            current_batch_translations.append(translated_segment)

            if not translated_segment.startswith("ERROR_") and global_idx_of_text < total_texts - 1:
                time.sleep(0.5)

        all_translated_texts.extend(current_batch_translations)

    print(f"\n全部 {total_texts} 段文本翻译完成。")
    return all_translated_texts


# --- 文件路径配置 ---
input_filepath = r"./uploads/input.srt"
output_filepath = r"./uploads/output.srt"

print(f"正在处理文件: {input_filepath}")
print(f"输出文件路径: {output_filepath}")

# --- 配置合并参数 ---
MAX_CHARS = 80
MAX_DURATION = 10

# --- 配置 SiliconFlow 翻译批次大小 ---
SILIFLOW_BATCH_SIZE = 1

# --- 配置输出双语字幕格式 ---
BILINGUAL_OUTPUT_FORMAT = 'two_lines'

try:
    if not os.path.exists(input_filepath):
        print(f"错误: 输入文件不存在: {input_filepath}")
    else:
        try:
            with open(input_filepath, 'r', encoding='utf-8') as f:
                srt_content = f.read()
        except UnicodeDecodeError:
            print("警告: UTF-8解码失败，尝试使用cp1252或其他常见编码。")
            try:
                with open(input_filepath, 'r', encoding='utf-8-sig') as f:
                    srt_content = f.read()
            except UnicodeDecodeError:
                with open(input_filepath, 'r', encoding='latin-1') as f:
                    srt_content = f.read()
            except Exception as e_inner:
                print(f"致命错误: 尝试多种编码仍无法读取文件: {e_inner}")
                srt_content = None
        except Exception as e:
            print(f"错误: 读取文件时发生未知错误: {e}")
            srt_content = None

        if srt_content:
            print("\n第一步: 合并和优化英文字幕段...")
            merged_srt_data = merge_srt_sentences_optimized(
                srt_content,
                max_chars_per_segment=MAX_CHARS,
                max_duration_sec_per_segment=MAX_DURATION
            )
            print(f"英文字幕段优化完成，共生成 {len(merged_srt_data)} 个合并段。")

            print("\n第二步: 提取文本进行翻译...")
            texts_to_translate = [item['text'] for item in merged_srt_data]

            if texts_to_translate:
                print(f"共 {len(texts_to_translate)} 个字幕段需要翻译。")
                print(f"开始使用 SiliconFlow API 翻译 (逐段独立请求处理)...")

                translated_texts = translate_texts_with_siliflow_batched(
                    texts_to_translate,
                    batch_size=SILIFLOW_BATCH_SIZE
                )

                print("翻译完成。")

                for i, item in enumerate(merged_srt_data):
                    if i < len(translated_texts):
                        item['translated_text'] = translated_texts[i]
                    else:
                        item['translated_text'] = ""

                print("\n第三步: 生成双语字幕文件...")
                new_srt_output = generate_new_srt(merged_srt_data, bilingual_format=BILINGUAL_OUTPUT_FORMAT)

                with open(output_filepath, 'w', encoding='utf-8') as f:
                    f.write(new_srt_output)
                print(f"成功将双语字幕保存到: {output_filepath}")
                print(f"合并参数: 最大字符数={MAX_CHARS}, 最大持续时间={MAX_DURATION}秒")
                print(f"翻译模型: {SILIFLOW_MODEL_NAME}")
                print(f"SiliconFlow 批次大小: {SILIFLOW_BATCH_SIZE} (实际为逐段请求，每次独立调用API)")
                print(f"双语输出格式: {BILINGUAL_OUTPUT_FORMAT}")
            else:
                print("没有可翻译的文本。")
        else:
            print("处理停止，เพราะ无法读取或获取SRT内容。")

except Exception as e:
    print(f"处理过程中发生意外错误: {type(e).__name__}: {e}")



