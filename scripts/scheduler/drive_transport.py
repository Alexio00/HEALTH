"""Bounded Drive JSON metadata calls; credentials and responses stay private."""
import json,urllib.error,urllib.request
class DriveStop(RuntimeError):pass
class NoRedirect(urllib.request.HTTPRedirectHandler):
    def redirect_request(self,*args,**kwargs):return None
class DriveTransport:
    def __init__(self,token):self.token=token;self.opener=urllib.request.build_opener(NoRedirect)
    def request(self,path,method='GET',body=None,content_type=None):
        if not isinstance(path,str) or not path.startswith('/drive/v3/') or any(ord(c)<32 for c in path) or '#' in path or method not in ('GET','POST','PATCH'):
            raise DriveStop('drive_metadata_request_rejected')
        headers={'Authorization':'Bearer '+self.token()}
        if content_type:headers['Content-Type']=content_type
        request=urllib.request.Request('https://www.googleapis.com'+path,data=body,headers=headers,method=method)
        try:
            with self.opener.open(request,timeout=60) as response:
                data=response.read(6*1024**2)
                if response.read(1):raise DriveStop('drive_metadata_response_limit')
                return json.loads(data)
        except urllib.error.HTTPError as e:raise DriveStop('drive_http_'+str(e.code)) from None
        except (urllib.error.URLError,TimeoutError):raise DriveStop('drive_metadata_outcome_uncertain') from None
