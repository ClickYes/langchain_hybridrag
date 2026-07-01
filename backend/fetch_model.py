from modelscope import snapshot_download
model_dir = snapshot_download(
  model_id='sentence-transformers/paraphrase-multilingual-mpnet-base-v2', 
  cache_dir='./models'
)