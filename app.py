import gradio as gr
import whisper
from transformers import BlipProcessor, BlipForConditionalGeneration
from PIL import Image

# Tiny models so Render won't crash
print("Loading models...")
whisper_model = whisper.load_model("tiny")
processor = BlipProcessor.from_pretrained("Salesforce/blip-image-captioning-base")
caption_model = BlipForConditionalGeneration.from_pretrained("Salesforce/blip-image-captioning-base")
print("Models loaded!")

def image_to_lyrics(img):
    if img is None:
        return "Please upload an image"
    inputs = processor(img, return_tensors="pt")
    out = caption_model.generate(**inputs)
    caption = processor.decode(out[0], skip_special_tokens=True)
    lyrics = f"[Verse]\nI see {caption}\n\n[Chorus]\nEvery picture tells a story\n{caption} in the light of glory"
    return lyrics

def audio_to_lyrics(audio):
    if audio is None:
        return "Please upload audio"
    result = whisper_model.transcribe(audio)
    return result["text"]

with gr.Blocks(title="INNOSTRANSLATE") as demo:
    gr.Markdown("# INNOSTRANSLATE - Image & Audio to Lyrics")
    with gr.Tab("Image to Lyrics"):
        img_in = gr.Image(type="pil", label="Upload Image")
        img_out = gr.Textbox(label="Lyrics", lines=8)
        btn1 = gr.Button("Generate")
        btn1.click(image_to_lyrics, img_in, img_out)
    with gr.Tab("Audio to Lyrics"):
        aud_in = gr.Audio(type="filepath", label="Upload MP3/WAV")
        aud_out = gr.Textbox(label="Lyrics", lines=8)
        btn2 = gr.Button("Transcribe")
        btn2.click(audio_to_lyrics, aud_in, aud_out)

demo.launch(server_name="0.0.0.0", server_port=10000)
