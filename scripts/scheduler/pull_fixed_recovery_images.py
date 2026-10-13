"""Pull immutable recovery images; bounded retry only for registry throttling."""
import json,subprocess,time
IMAGES=(
 'postgres@sha256:2d2b8998d31037bf721cfdf764d76ba74171b4fab3431b7f72c27c56ddbdf9e3',
 'public.ecr.aws/supabase/postgres@sha256:06ddc7962e11ab0f4f0334fd05671e97c30ea202f6e6a7113800bd3d6e416108',
 'public.ecr.aws/supabase/gotrue@sha256:1736a63078f5922b198c4cbe50f80ab9a2d3b54fe8b7b6cfb2e9dc5dbbc12c6b',
 'python@sha256:34386ef0cb081344d7ec1c103ba398e6e9f64e9ab3a1509accc92a4e24a07258')
DELAYS=(15,45,120)
class ImageStop(RuntimeError):pass
def pull(image,run=subprocess.run,sleep=time.sleep):
 if image not in IMAGES:raise ImageStop('unreviewed_image_rejected')
 for attempt in range(len(DELAYS)+1):
  p=run(['docker','pull',image],capture_output=True,timeout=600)
  if p.returncode==0:
   r=run(['docker','image','inspect',image,'--format','{{json .RepoDigests}}'],capture_output=True,timeout=30)
   if r.returncode:raise ImageStop('fixed_image_readback_failed')
   refs=json.loads(r.stdout)
   # Docker Hub normalizes official images to docker.io/library/<name>.
   normalized='docker.io/library/'+image if '/' not in image.split('@')[0] else image
   if image not in refs and normalized not in refs:raise ImageStop('fixed_image_digest_readback_mismatch')
   return attempt+1
  text=(p.stdout+p.stderr).decode('utf-8',errors='replace').lower()
  if not ('toomanyrequests' in text or 'rate exceeded' in text or '429 too many requests' in text):raise ImageStop('fixed_image_pull_failed_nonretryable')
  if attempt==len(DELAYS):raise ImageStop('fixed_image_registry_throttling_exhausted')
  print(json.dumps({'stage':'fixed_image_registry_throttling','attempt':attempt+1,'retry_after_seconds':DELAYS[attempt],'image_digest':image.split('@')[1]}),flush=True)
  sleep(DELAYS[attempt])
if __name__=='__main__':
 try:
  for image in IMAGES:print(json.dumps({'stage':'fixed_image_digest_verified','image':image,'attempts':pull(image)}),flush=True)
 except Exception as e:
  print(json.dumps({'status':'STOPPED','safe_reason':str(e) if isinstance(e,ImageStop) else type(e).__name__}));raise SystemExit(2)
