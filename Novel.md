
### 1.  Pipeline system 
	`.md → AI translate → new .md → reader app`
### 2.  Choose Ai Model
    1.  Ollama Local Model 
	    • Qwen 3.5 (7B / 14B) 
	    • Llama 3 / 4 
	    • Gemma 4 
		- Translation-specific model 
			• translategemma 
			• NLLB
	  2. Online Free API 
		  • Google Gemini (free tier) 
		  • Cohere Aya (multilingual) 
		  • Mistral best choose 
		  • Google Translate API 
		  • NLLB-200 (Meta) 
			- Local 
				- Qwen 3.5 + Ollam 
			- Online 
				- Gemini
### 3.  Translation Code Logic
	1.  Ollama (Local) import requests
```import requests
		
		def translate(text):
		    response = requests.post(
		        "http://localhost:11434/api/generate",
		        json={
		            "model": "qwen:7b",
		            "prompt": f"Translate Chinese to Myanmar:\n{text}",
		            "stream": False
			        }
			)
		    return response.json()["response"]
```

	2. Gemini API
```		import google.generativeai as genai

genai.configure(api_key="YOUR_API_KEY")

model = genai.GenerativeModel("gemini-1.5-flash")

def translate(text):
    prompt = f"Translate Chinese to Myanmar:\n{text}"
    response = model.generate_content(prompt)
    return response.text 
```

###  4. Processing .md files. import os
```import os

input_folder = "chinese_md"
output_folder = "myanmar_md"

for file in os.listdir(input_folder):
    with open(f"{input_folder}/{file}", "r", encoding="utf-8") as f:
        content = f.read()

    translated = translate(content)

    with open(f"{output_folder}/{file}", "w", encoding="utf-8") as f:
        f.write(translated)

```

### 5.  Optimizations that must be done in practice
    
    1.  Segmented translationSegmented translation
		 Don't throw the whole novel away at once.
```			def split_text(text, max_len=1000):
				return [text[i:i+max_len] for i in range(0, len(text), max_len)]
 ```
		  2. Prompt optimization
			- Translate Chinese novel into natural Myanmar language. 
			- Keep names consistent. 
			- Keep markdown format.
### 6. Received Reader App
	- You already have
			 - .md translated files
    
	- Next：
	    - Modify your repo structure
```			
			/books
			  /book1
			    chapter1.md
			    chapter2.md
```    
    - Reader reads .md files
	    - To do
			- Markdown parser
			- Text UI
	- For example:
		- Flutter
			- markdown widget
		- Web
			- marked.js
	- Function
		- next / prev chapter
		- font size
		- dark mode
	- It will then become a novel_reader type.
```
     	[Chinese md]
     				↓
     	[AI translation (Ollama / API)]
     				↓
     	[Myanmar md]
     				↓
     	[Reader App UI]
    
  ```
