"""블로거 리프레시 토큰 1회 발급 도구 (내 PC에서 실행)
사전 준비: Google Cloud 콘솔 → 프로젝트 생성 → 'Blogger API v3' 사용 설정
          → OAuth 동의 화면(외부, 게시 상태 '프로덕션'으로) → 사용자 인증 정보 → OAuth 클라이언트 ID(데스크톱 앱)
실행: python tools/blogger_auth.py <CLIENT_ID> <CLIENT_SECRET>
→ 브라우저에서 블로그 소유 구글 계정으로 허용 → 출력된 REFRESH_TOKEN을 GitHub Secrets에 저장
표준 라이브러리만 사용합니다.
"""
import http.server, json, sys, urllib.parse, urllib.request, webbrowser

PORT = 8765
SCOPE = 'https://www.googleapis.com/auth/blogger'


def main(cid, secret):
    redirect = f'http://127.0.0.1:{PORT}/'
    auth = 'https://accounts.google.com/o/oauth2/v2/auth?' + urllib.parse.urlencode(dict(
        client_id=cid, redirect_uri=redirect, response_type='code', scope=SCOPE, access_type='offline', prompt='consent'))
    code = {}

    class H(http.server.BaseHTTPRequestHandler):
        def do_GET(self):
            q = urllib.parse.parse_qs(urllib.parse.urlparse(self.path).query)
            code['c'] = q.get('code', [None])[0]
            self.send_response(200); self.send_header('Content-Type', 'text/html; charset=utf-8'); self.end_headers()
            self.wfile.write('완료! 이 창을 닫고 터미널을 확인하세요.'.encode())

        def log_message(self, *a):
            pass

    print('브라우저가 열리지 않으면 이 주소를 직접 여세요:\n', auth)
    webbrowser.open(auth)
    srv = http.server.HTTPServer(('127.0.0.1', PORT), H)
    while not code.get('c'):
        srv.handle_request()
    data = urllib.parse.urlencode(dict(code=code['c'], client_id=cid, client_secret=secret,
                                       redirect_uri=redirect, grant_type='authorization_code')).encode()
    tok = json.load(urllib.request.urlopen('https://oauth2.googleapis.com/token', data))
    print('\nBLOGGER_REFRESH_TOKEN =', tok.get('refresh_token'))
    at = tok['access_token']
    req = urllib.request.Request('https://www.googleapis.com/blogger/v3/users/self/blogs', headers={'Authorization': 'Bearer ' + at})
    for b in json.load(urllib.request.urlopen(req)).get('items', []):
        print(f"BLOGGER_BLOG_ID = {b['id']}   ({b['name']}  {b['url']})")


if __name__ == '__main__':
    main(sys.argv[1], sys.argv[2])
