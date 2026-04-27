import os
os.environ["GRADIO_ANALYTICS_ENABLED"] = "False"
os.environ["no_proxy"] = "localhost,127.0.0.1,::1"
os.environ["GRADIO_SERVER_NAME"] = "0.0.0.0"
import argparse
import gc
import json
import shutil
import glob
import subprocess
import threading
import time
import traceback
import uuid
from enum import Enum
import queue
from functools import partial
import zipfile
import requests
from port import gradio_port,api_port
from mel.mel_inf import proc_folder

# --- Third-party library imports ---
import torch
import cv2
import gradio as gr
import uvicorn
from fastapi import FastAPI, Query, Request
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel
from typing import Optional, Annotated # MODIFIED FOR CYTHON

from moviepy.editor import VideoFileClip, AudioFileClip, CompositeAudioClip
from audio_separator.separator import Separator

# --- Local application imports ---
# Assuming these are in the correct path
import service.trans_dh_service
from h_utils.custom import CustomError
from y_utils.config import GlobalConfig
from y_utils.logger import logger


# --- Environment and Global Setup ---

ROOT_DIR = os.path.dirname(os.path.abspath(__file__))

front = ""
back = ""

voices = ["使用上传的视频驱动"]
for name in os.listdir("face_cache"):
    voices.append(name.replace(".pt",""))

def update_voices():

    voices = ["使用上传的视频驱动"]
    for name in os.listdir("face_cache"):
        voices.append(name.replace(".pt",""))
    
    return {"choices":voices, "__type__": "update"}

def save_name_v(name,ref_audio_input):

    if not name or name == "":
        gr.Info("名称不能为空")
        return False
    
    if not ref_audio_input or ref_audio_input == "":
        gr.Info("驱动音频不能为空")
        return False
    

    bname = os.path.splitext(ref_audio_input)[-1]
    
    shutil.copyfile(ref_audio_input,f"log/{name}{bname}")
    
    torch.save({"audio":f"log/{name}{bname}"},f'face_cache/{name}.pt')

    gr.Info("角色保存成功,存放位置为face_cache目录")


def down_video(input_path, output_path, resolution_scale_factor=0.7, target_fps=24):
    """
    使用 MoviePy 对视频进行等比例降低分辨率并设置帧率。

    参数:
    input_path (str): 输入视频文件的路径。
    output_path (str): 处理后视频的保存路径。
    resolution_scale_factor (float): 分辨率的缩放因子。
                                     例如，要将分辨率降低一半（如 480p -> 240p），此值为 0.5。
    target_fps (int): 输出视频的目标帧率。
    """
    try:
        # 1. 加载视频文件
        print(f"正在加载视频: {input_path}")
        clip = VideoFileClip(input_path)
        
        # 打印原始分辨率和帧率
        original_width, original_height = clip.size
        print(f"原始分辨率: {original_width}x{original_height}")
        print(f"原始帧率: {clip.fps}")

        # 2. 等比例降低分辨率
        # 使用 resize 方法并传入一个浮点数作为缩放因子
        print(f"正在将分辨率缩放 {resolution_scale_factor} 倍...")
        resized_clip = clip.resize(resolution_scale_factor)
        
        new_width, new_height = resized_clip.size
        print(f"新的分辨率: {new_width}x{new_height}")

        # 3. 设置帧率并写入文件
        # 在 write_videofile 方法中，通过 fps 参数设置新的帧率
        print(f"正在设置帧率为 {target_fps} 并写入文件...")
        resized_clip.write_videofile(output_path, fps=target_fps)
        
        print(f"处理完成！视频已保存至: {output_path}")

    except Exception as e:
        print(f"处理过程中发生错误: {e}")


if_gfpgan_default = True

def c_gfpgan(value):

    global if_gfpgan_default

    if_gfpgan_default = value

def download_file(url, local_filename):
    """
    使用 requests 模块下载文件并显示进度。

    :param url: 文件的 URL
    :param local_filename: 保存到本地的文件名
    """
    # if os.path.exists(local_filename):
    #     print(f"文件 {local_filename} 已存在，跳过下载。")
    #     return

    try:
        with requests.get(url, stream=True) as r:
            r.raise_for_status()  # 如果请求失败则引发 HTTPError 异常
            total_size_in_bytes = int(r.headers.get('content-length', 0))
            block_size = 1024  # 1 Kibibyte

            print(f"正在下载: {local_filename}")
            with open(local_filename, 'wb') as f:
                for chunk in r.iter_content(chunk_size=block_size):
                    f.write(chunk)
            print(f"下载完成: {local_filename}")

    except requests.exceptions.RequestException as e:
        print(f"下载 {local_filename} 时出错: {e}")

# --- Utility Functions ---

def zip_directory(folder_path, zip_path):
    print(f"Compressing '{folder_path}' to '{zip_path}'...")
    with zipfile.ZipFile(zip_path, 'w', zipfile.ZIP_DEFLATED) as zipf:
        for root, dirs, files in os.walk(folder_path):
            for file in files:
                file_path = os.path.join(root, file)
                arcname = os.path.relpath(file_path, start=folder_path)
                zipf.write(file_path, arcname=arcname)
    print("Compression complete!")

def resize_video(input_path, output_path, target_height, target_fps=None):
    try:
        print(f"Processing video: {input_path}")
        video_clip = VideoFileClip(input_path)
        original_fps = video_clip.fps
        print(f"Original resolution: {video_clip.w}x{video_clip.h}, Original FPS: {original_fps:.2f}")
        
        print(f"Resizing video height to {target_height}p...")
        resized_clip = video_clip.resize(height=target_height)
        
        final_fps = target_fps if target_fps is not None else original_fps
        if target_fps is not None:
            print(f"Adjusting frame rate to {final_fps} fps...")

        print(f"Saving to: {output_path}")
        resized_clip.write_videofile(
            output_path, 
            fps=final_fps,
            codec="libx264", 
            audio_codec="aac"
        )
        video_clip.close()
        resized_clip.close()
        print("Video resizing complete!")
    except Exception as e:
        print(f"Error processing video: {e}")

def merge_with_ffmpeg_python(video_path, output_path="output_new.mp4"):
    audio_path = back
    video_clip = VideoFileClip(video_path)
    original_audio = video_clip.audio
    new_audio = AudioFileClip(audio_path)
    mixed_audio = CompositeAudioClip([original_audio, new_audio])
    final_clip = video_clip.set_audio(mixed_audio)
    final_clip.write_videofile(output_path, codec="libx264", audio_codec="aac")
    video_clip.close()
    original_audio.close()
    new_audio.close()
    final_clip.close()
    return output_path, output_path

def split_audio(ori_audio):
    # separator = Separator()
    # separator.load_model()
    # output_files = separator.separate(ori_audio)
    # print(f"Separated audio files: {output_files}")

    proc_folder(ori_audio)

    global front, back
    front = "mel/volcal.wav"
    back = "mel/back.wav"
    return front

def clear_directory(path):
    try:
        if os.path.exists(path):
            shutil.rmtree(path)
        os.makedirs(path)
    except OSError as e:
        print(f"Error clearing directory {path}: {e}")

def display_video_path(video):
    return video

def display_audio_path(audio):
    return audio

def write_video_gradio(
    output_imgs_queue, temp_dir, result_dir, work_id, audio_path,
    result_queue, width, height, fps, watermark_switch=0,
    digital_auth=0, temp_queue=None
):
    output_mp4 = os.path.join(temp_dir, f"{work_id}-t.mp4")
    fourcc = cv2.VideoWriter_fourcc(*"mp4v")
    result_path = os.path.join(result_dir, f"{work_id}-r.mp4")
    video_write = cv2.VideoWriter(output_mp4, fourcc, fps, (width, height))
    print("Custom VideoWriter initialized.")
    try:
        while True:
            state, reason, value_ = output_imgs_queue.get()
            if isinstance(state, bool) and state:
                logger.info(f"Video frame queue processing finished for [{work_id}]")
                video_write.release()
                break
            elif isinstance(state, bool) and not state:
                logger.error(f"Error in video frame queue for [{work_id}]: {reason}")
                raise CustomError(reason)
            for result_img in value_:
                video_write.write(result_img)
        
        command = f"ffmpeg -loglevel warning -y -i {audio_path} -i {output_mp4} -c:a aac -c:v libx264 -crf 15 -strict -2 {result_path}"
        logger.info(f"Executing ffmpeg command: {command}")
        subprocess.call(command, shell=True)
        print(f"Video result saved in {os.path.realpath(result_path)}")
        result_queue.put([True, result_path])
    except Exception as e:
        logger.error(f"VideoWriter [{work_id}] failed: {e}")
        result_queue.put([False, f"VideoWriter failed: {e}"])
    logger.info("Custom VideoWriter process finished.")

service.trans_dh_service.write_video = write_video_gradio

class VideoProcessor:
    def __init__(self):
        self.task = service.trans_dh_service.TransDhTask()
        self.basedir = GlobalConfig.instance().result_dir
        self.is_initialized = False
        self._initialize_service()
        print("API available at http://localhost:8000/docs")

    def _initialize_service(self):
        logger.info("Initializing trans_dh_service...")
        try:
            time.sleep(2)
            self.is_initialized = True
            logger.info("trans_dh_service initialized.")
        except Exception as e:
            logger.error(f"Failed to initialize trans_dh_service: {e}")
    
    def _ensure_task_ready(self):
        """确保 task 可用，如果已被清理则重新创建"""
        if self.task is None or (hasattr(self.task, '_cleaned') and self.task._cleaned):
            logger.info("TransDhTask was cleaned up, reinitializing...")
            self.task = service.trans_dh_service.TransDhTask()
            logger.info("TransDhTask reinitialized")
    
    def process_video_batch(self, audio_file, video_file, steps, if_gfpgan):
        self._ensure_task_ready()

        clear_directory("change")

        job_id = str(uuid.uuid4())
        work_dir = os.path.join("change", job_id)
        os.makedirs(work_dir, exist_ok=True)

        
        # self.task.batch_size = steps
        shutil.copy2(audio_file, f"{work_dir}/test.wav")
        shutil.copy2(video_file, f"{work_dir}/input.mp4")
        
        while not self.is_initialized:
            time.sleep(1)

        code = os.path.splitext(os.path.basename(f"{work_dir}/input.mp4"))[0]
        try:
            g_w = 1 if if_gfpgan else 0
            self.task.task_dic[code] = ""
            self.task.face_id = 0
            self.task.work(f"{work_dir}/test.wav", f"{work_dir}/input.mp4", code, 0, 0, g_w, 1)
            result_path = self.task.task_dic[code][2]
            
            if torch.cuda.is_available():
                torch.cuda.empty_cache()
            gc.collect()
            return result_path
        except Exception as e:
            logger.error(f"Error during batch processing: {e}")
            raise gr.Error(str(e))

    def process_video(
        self, ifface, audio_file, video_file, steps, if_gfpgan,sface="使用上传的视频驱动",low=0,face_id=0,output_filename: Optional[str] = None
    ):
        self._ensure_task_ready()
        
        job_id = str(uuid.uuid4())
        work_dir = os.path.join("change", job_id)
        os.makedirs(work_dir, exist_ok=True)
        os.makedirs("生成结果", exist_ok=True)

        # with open("face_lib/face.json", "w", encoding="utf-8") as file:
        #     json.dump({"face_id":int(face_id)}, file, ensure_ascii=False, indent=4)

        try:

            
            if sface != "使用上传的视频驱动":

                mypt = torch.load(f"face_cache/{sface}.pt",weights_only=False)

                video_file = mypt["audio"]

            print(video_file)

            video_file_processed = os.path.join(work_dir, "input.mp4")
            audio_file_processed = os.path.join(work_dir, "test.wav")

            if ifface:
                shutil.copy2(video_file, video_file_processed)
            else:
                resize_video(video_file, video_file_processed, 720, 24)

            low = float(low)

            if low == 0.0:
                low = 0


            print(f"face_id=============={face_id}")

            if face_id == -1:

                steps = 4

            if low != 0:
                down_video(video_file_processed, f"{work_dir}/input_low.mp4", low, 24)
                video_file_processed = f"{work_dir}/input_low.mp4"

            shutil.copy2(audio_file, audio_file_processed)
            self.task.batch_size = steps
            self.task.face_id = face_id

            while not self.is_initialized:
                logger.info("Service not yet initialized, waiting...")
                time.sleep(1)

            code = os.path.splitext(os.path.basename(video_file_processed))[0]
            start_time = time.time()
            g_w = 1 if if_gfpgan else 0
            self.task.task_dic[code] = ""
            self.task.work(audio_file_processed, video_file_processed, code, 0, 0, g_w, 1,face_id)
            result_path = self.task.task_dic[code][2]

            print(f"result_path: {result_path}")

            # final_filename = output_filename if output_filename else "new.mp4"
            # final_output_path = os.path.join("save", final_filename)
            # os.makedirs("save", exist_ok=True)
            # shutil.copy2(result_path, final_output_path)

            final_save = f"生成结果/r-{int(time.time())}.mp4"

            shutil.copy2(result_path,final_save)

            duration = time.time() - start_time
            if torch.cuda.is_available():
                torch.cuda.empty_cache()
                torch.cuda.ipc_collect()
            gc.collect()
            yield final_save, f"Time taken: {duration:.2f} seconds ", final_save
        finally:
            print(f"Cleaning up temporary directory: {work_dir}")
            shutil.rmtree(work_dir, ignore_errors=True)

def start_gradio(processor: VideoProcessor):

    def add_box(count):

        return count + 1
    with gr.Blocks() as app:
        gr.Markdown("## HeyGem Digital Human Onnx - 数字人优化版 原生支持50系 不得使用本软件进行任何违法活动，使用者需自行承担法律责任。")
        gr.Markdown('# 刘悦的技术博客(B站/Youtube 同名) https://t.zsxq.com/IrQPr')
        # gr.Markdown('# 公众号：小威的软件库，QQ：1400534610')
        # gr.Markdown('# 新思维heygem数字人助手 联系人：赵先生 联系电话：158-5426-9366（微信同号）')
        # gr.Markdown("# 支持代理或者贴牌，微信公众号:小强仔特效师，更多项目  https://link3.cc/shuziren  不得使用本软件进行任何违法活动，使用者需自行承担法律责任。")
        with gr.Accordion("数字人生成", open=True):
            with gr.Row():
                with gr.Column():
                    video_in = gr.Video(label="上传视频,如果报错,下面有地址就行，直接生成")
                    video_url = gr.Textbox(label="视频地址")

                    v_dropdown = gr.Dropdown(label="角色列表",choices=voices,value="使用上传的视频驱动",interactive=True)
                    refresh_voices_button = gr.Button("刷新角色列表")
                    refresh_voices_button.click(fn=update_voices, inputs=[], outputs=[v_dropdown])
                    new_name_v = gr.Textbox(label="输入角色名称", lines=1, placeholder="输入新的角色名称.", value='')
                    save_button = gr.Button("保存角色")
                    save_button.click(save_name_v,inputs=[new_name_v,video_in])

                    ifface = gr.Checkbox(label="是否使用原始分辨率和帧率，如果不勾选，那就用720P和24帧提高推理速度", value=True)
                    if_gfpgan = gr.Checkbox(label="是否使用GFPGAN 1.4面部超分，开了就会慢，而且脸可能有点假", value=False)
                    steps = gr.Number(
                        label="推理批次 (FP16优化后: 16=推荐, 32=极速。多人模式face_id=-1时自动设为4)",
                        value=4,
                        interactive=True,
                        minimum=1,
                        maximum=64
                    )
                    low = gr.Number(label="分辨率的缩放因子。例如，要将分辨率降低一半（如 480p -> 240p），此值为 0.5。默认为0,不缩放", value=0, interactive=True)
                    if_gfpgan.change(c_gfpgan,[if_gfpgan],[])

                    # # 多人模式：自动调整 batch_size
                    # def update_steps_for_multi_face(face_id_value):
                    #     """多人模式自动设置 batch_size=4"""
                    #     if face_id_value == -1:
                    #         return 4
                    #     else:
                    #         return 16

                    # face_id.change(update_steps_for_multi_face, [face_id], [steps])
                with gr.Column():
                    audio_in = gr.Audio(type="filepath", label="驱动音频,如果报错,下面有地址就行，直接生成")
                    audio_url = gr.Textbox(label="音频地址")
                    split_button = gr.Button("分离背景音，如果需要的话")

                with gr.Column():
                    face_id = gr.Number(label="输入驱动人脸序号,默认0为第一张脸,1为第二张,顺序是由左至右,从上到下,设置-1为所有脸驱动",value=0,interactive=True)
                    make_button = gr.Button("开始生成", variant="primary")
                    output_video = gr.Video(label="生成结果",interactive=True)
                    merge_button = gr.Button("合并背景音，如果需要的话")
                    output_time = gr.Textbox(label="任务信息", interactive=True)
                    output_file = gr.File(label="下载视频", interactive=True)

        text_count = gr.State(2)
        task_states = gr.State([True] * 900)  # 用于跟踪每个任务是否被删除
        file_states = gr.State({})  # 用于保存已上传的文件
        
        with gr.Accordion("批量任务,是否超分,使用上面的参数"):
            add_btn = gr.Button("添加任务")
            add_btn.click(add_box, text_count, text_count)

            @gr.render(inputs=[text_count, task_states, file_states])
            def render_count(count, states, files):
                boxes = []
                delete_buttons = []
                
                def update_file_state(task_index, file_type, file_value):
                    """更新文件状态"""
                    key = f"{task_index}_{file_type}"
                    files[key] = file_value
                    return files
                
                for i in range(count):
                    if i < len(states) and states[i]:  # 只显示未删除的任务
                        with gr.Row():
                            # 从状态中获取已保存的文件值
                            video_key = f"{i}_video"
                            audio_key = f"{i}_audio"
                            video_value = files.get(video_key, None)
                            audio_value = files.get(audio_key, None)
                            
                            box = gr.File(label=f"上传视频_{i}", interactive=True, value=video_value)
                            text_p = gr.File(label=f"上传音频_{i}", interactive=True, value=audio_value)
                            delete_btn = gr.Button(f"删除任务_{i}", variant="secondary", size="sm")
                            
                            # 为文件上传添加事件处理
                            def create_file_handler(task_index, file_type):
                                def handle_file_upload(file_value):
                                    return update_file_state(task_index, file_type, file_value)
                                return handle_file_upload
                            
                            box.upload(
                                create_file_handler(i, "video"),
                                inputs=[box],
                                outputs=[file_states]
                            )
                            
                            text_p.upload(
                                create_file_handler(i, "audio"),
                                inputs=[text_p],
                                outputs=[file_states]
                            )
                            
                            # 为删除按钮添加点击事件
                            def create_delete_handler(task_index):
                                def delete_task(current_states, current_files):
                                    new_states = current_states.copy()
                                    new_states[task_index] = False
                                    # 清理对应的文件状态
                                    new_files = current_files.copy()
                                    video_key = f"{task_index}_video"
                                    audio_key = f"{task_index}_audio"
                                    if video_key in new_files:
                                        del new_files[video_key]
                                    if audio_key in new_files:
                                        del new_files[audio_key]
                                    return new_states, new_files
                                return delete_task
                            
                            delete_btn.click(
                                create_delete_handler(i),
                                inputs=[task_states, file_states],
                                outputs=[task_states, file_states]
                            )
                            
                            boxes.append(box)
                            boxes.append(text_p)
                            delete_buttons.append(delete_btn)

                def merge(*args):
                    clear_directory("批量任务")

                    num = 0
                    file_list = []
                    # 只处理未删除的任务

                    valid_args = args

                    print(valid_args)
                    print(555555555555555555555555)

                    # 【逻辑修正】: 修正 zip 的用法，正确地按组处理参数
                    for a, b, in zip(
                        valid_args[0::2], 
                        valid_args[1::2],
                    ):

                        if a == "" or b == "" or a is None or b is None:
                            pass
                        else:
                            res = processor.process_video_batch(b,a,4,if_gfpgan_default)
                            shutil.copy2(res,f"批量任务/job_{num}.mp4")
                            file_list.append(f"批量任务/job_{num}.mp4")
                            num += 1

                    zip_directory("批量任务","all.zip")

                    yield "批量任务完成,存储在批量任务目录",file_list,"all.zip"

                merge_btn.click(merge,boxes,[output,file_list,file_zip])

            merge_btn = gr.Button("开始批量任务")
            output = gr.Textbox(label="批量任务结果")
            file_list = gr.Gallery(interactive=True)
            file_zip = gr.File(label="下载全部结果")
                    
            

            video_in.change(display_video_path, inputs=video_in, outputs=video_url)
            audio_in.change(display_audio_path, inputs=audio_in, outputs=audio_url)
            split_button.click(split_audio, inputs=[audio_in], outputs=[audio_in])
            make_button.click(
                processor.process_video,
                inputs=[ifface, audio_url, video_url, steps, if_gfpgan,v_dropdown,low,face_id],
                outputs=[output_video, output_time, output_file]
            )
            merge_button.click(
                merge_with_ffmpeg_python,
                inputs=[output_video],
                outputs=[output_video, output_file]
            )
    print(f"Starting Gradio UI on http://0.0.0.0:{gradio_port}")
    app.queue().launch(inbrowser=False, server_port=gradio_port, server_name="0.0.0.0")

class ProcessVideoRequest(BaseModel):
    audio_file: str
    video_file: str
    ifface: Optional[bool] = False
    if_gfpgan: Optional[bool] = False
    steps: Optional[int] = 16  # 默认使用16，FP16优化后的推荐值
    low: Optional[float] = 0.0
    face_id: Optional[int] = 0

def setup_fastapi_app(processor: VideoProcessor):
    api = FastAPI()
    os.makedirs("save", exist_ok=True)
    api.mount("/results", StaticFiles(directory="生成结果"), name="results")

    def process_video_logic(req: Request, audio_file: str, video_file: str, ifface: bool, if_gfpgan: bool, steps: int,low: float,face_id:int):
        logger.info(f"API request: audio='{audio_file}', video='{video_file}'")

        print(f"api: low {low}")

        if "http://" in video_file or "https://" in video_file:

            video_url = video_file
            video_filename = "change/d.mp4"
            download_file(video_url, video_filename)
            video_file = video_filename

        if "http://" in audio_file or "https://" in audio_file:

            audio_url = audio_file
            audio_filename = "change/d.wav"
            download_file(audio_url, audio_filename)
            audio_file = audio_filename


        if not os.path.exists(video_file):
            return {"status": "error", "message": f"Video file not found: {video_file}"}
        if not os.path.exists(audio_file):
            return {"status": "error", "message": f"Audio file not found: {audio_file}"}
        try:
            unique_filename = f"{uuid.uuid4()}.mp4"
            final_result = None
            generator = processor.process_video(
                ifface, audio_file, video_file, steps, if_gfpgan,"使用上传的视频驱动",low,face_id,
                output_filename=unique_filename
            )
            for result in generator:
                final_result = result
            if final_result:
                output_path, message, _ = final_result
                video_url = req.url_for('results', path=os.path.basename(output_path))
                return {
                    "status": "success",
                    "message": message,
                    "output_video_url": str(video_url)
                }
            else:
                return {"status": "error", "message": "Processing failed to produce a result."}
        except Exception as e:
            logger.error(f"API Error: {e}")
            traceback.print_exc()
            return {"status": "error", "message": str(e)}

    @api.post("/", summary="Generate video via POST")
    def generate_video_post(req_body: ProcessVideoRequest, req: Request):
        return process_video_logic(
            req, req_body.audio_file, req_body.video_file, 
            req_body.ifface, req_body.if_gfpgan, req_body.steps, req_body.low,req_body.face_id
        )

    @api.get("/", summary="Generate video via GET")
    def generate_video_get(
        req: Request,
        audio_file: Annotated[str, Query(description="Absolute path to the audio file")],
        video_file: Annotated[str, Query(description="Absolute path to the video file")],
        ifface: Annotated[bool, Query(description="Use original resolution and framerate")] = False,
        if_gfpgan: Annotated[bool, Query(description="Enable GFPGAN face enhancement")] = False,
        steps: Annotated[int, Query(description="Processing batch size")] = 4,
        low: Annotated[float, Query(description="Processing batch size")] = 0.0,
        face_id: Annotated[int, Query(description="Processing batch size")] = 0,
    ):
        
        return process_video_logic(
            req, audio_file, video_file, ifface, if_gfpgan, steps,low,face_id
        )

    # ── GPU 显存管理端点 ──

    @api.post("/api/v1/gpu/release", summary="Release GPU memory")
    def release_gpu():
        """释放 HeyGem 所有 GPU 显存占用（包括 WeNet 和 DigitalHuman 模型）"""
        try:
            # 记录清理前的 GPU 状态
            allocated_before = 0.0
            reserved_before = 0.0
            if torch.cuda.is_available():
                allocated_before = torch.cuda.memory_allocated() / 1024 / 1024
                reserved_before = torch.cuda.memory_reserved() / 1024 / 1024

            released_models = []

            # 1. 释放 VideoProcessor 中的 TransDhTask（核心模型和子进程）
            try:
                if hasattr(processor, 'task') and processor.task is not None:
                    result = processor.task.cleanup()
                    if result:
                        released_models.extend(result)
                        logger.info(f"TransDhTask cleanup: {result}")
                    else:
                        logger.warning("TransDhTask cleanup returned False (already cleaned or error)")
            except Exception as e:
                logger.error(f"Error releasing TransDhTask: {e}")

            # 2. 尝试释放单例（如果存在）
            try:
                from service.trans_dh_service import TransDhTask
                if hasattr(TransDhTask, '_instance') and TransDhTask._instance is not None:
                    if TransDhTask.reset_instance():
                        released_models.append("TransDhTask singleton")
            except Exception as e:
                pass

            # 3. 强制垃圾回收和显存清理
            gc.collect()
            if torch.cuda.is_available():
                torch.cuda.empty_cache()
                torch.cuda.synchronize()

            # 记录清理后的 GPU 状态
            allocated_after = 0.0
            reserved_after = 0.0
            if torch.cuda.is_available():
                allocated_after = torch.cuda.memory_allocated() / 1024 / 1024
                reserved_after = torch.cuda.memory_reserved() / 1024 / 1024

            logger.info(
                f"GPU release: allocated {allocated_before:.1f}→{allocated_after:.1f}MB, "
                f"reserved {reserved_before:.1f}→{reserved_after:.1f}MB, "
                f"released: {released_models}"
            )

            return {
                "status": "success",
                "message": "GPU memory released successfully",
                "memory_before_mb": {
                    "allocated": round(allocated_before, 2),
                    "reserved": round(reserved_before, 2)
                },
                "memory_after_mb": {
                    "allocated": round(allocated_after, 2),
                    "reserved": round(reserved_after, 2)
                },
                "released_models": released_models,
                "note": "Next request will trigger model reloading (cold start ~5-10s)"
            }
        except Exception as e:
            logger.error(f"GPU release failed: {e}")
            return {
                "status": "error",
                "message": str(e)
            }

    @api.get("/api/v1/gpu/status", summary="Get GPU status")
    def gpu_status():
        """查询当前 GPU 显存状态"""
        # 获取显存信息
        allocated_mb = 0.0
        reserved_mb = 0.0
        max_allocated_mb = 0.0
        cuda_available = torch.cuda.is_available()

        if cuda_available:
            allocated_mb = torch.cuda.memory_allocated() / 1024 / 1024
            reserved_mb = torch.cuda.memory_reserved() / 1024 / 1024
            max_allocated_mb = torch.cuda.max_memory_allocated() / 1024 / 1024

        # 检查 TransDhTask 是否已初始化
        transdh_initialized = False
        try:
            from service.trans_dh_service import TransDhTask
            transdh_initialized = hasattr(TransDhTask, '_instance') and TransDhTask._instance is not None
        except:
            pass

        return {
            "cuda_available": cuda_available,
            "memory_mb": {
                "allocated": round(allocated_mb, 2),
                "reserved": round(reserved_mb, 2),
                "max_allocated": round(max_allocated_mb, 2)
            },
            "models": {
                "transdh_initialized": transdh_initialized
            }
        }

    return api

def run_fastapi(api: FastAPI):
    print(f"Starting FastAPI server on http://0.0.0.0:{api_port}")
    uvicorn.run(api, host="0.0.0.0", port=api_port)

def main():
    processor = VideoProcessor()
    fastapi_app = setup_fastapi_app(processor)
    
    # 检查是否只启动 API 模式（通过环境变量控制）
    api_only = os.environ.get("HEYGEM_API_ONLY", "false").lower() == "true"
    
    if api_only:
        # 只启动 API，不启动 Gradio
        print(f"Starting HeyGem in API-only mode on http://0.0.0.0:{api_port}")
        print(f"GPU release endpoint: POST http://localhost:{api_port}/api/v1/gpu/release")
        print(f"GPU status endpoint:  GET  http://localhost:{api_port}/api/v1/gpu/status")
        uvicorn.run(fastapi_app, host="0.0.0.0", port=api_port)
    else:
        # 同时启动 API 和 Gradio
        api_thread = threading.Thread(target=run_fastapi, args=(fastapi_app,), daemon=True)
        api_thread.start()
        start_gradio(processor)

if __name__ == '__main__':
    main()