import AppKit

// Local vector illustrations for the learning guide; these are not AWS screenshots.
let output = URL(fileURLWithPath: CommandLine.arguments[1], isDirectory: true)
try FileManager.default.createDirectory(at: output, withIntermediateDirectories: true)
let ink = NSColor(calibratedRed: 0.10, green: 0.17, blue: 0.28, alpha: 1)
let muted = NSColor(calibratedRed: 0.36, green: 0.42, blue: 0.51, alpha: 1)
let blue = NSColor(calibratedRed: 0.14, green: 0.37, blue: 0.82, alpha: 1)
let green = NSColor(calibratedRed: 0.03, green: 0.48, blue: 0.40, alpha: 1)
let orange = NSColor(calibratedRed: 0.70, green: 0.34, blue: 0.08, alpha: 1)
let pale = NSColor(calibratedRed: 0.94, green: 0.96, blue: 0.99, alpha: 1)

func box(_ x: CGFloat, _ y: CGFloat, _ w: CGFloat, _ h: CGFloat, _ fill: NSColor, _ border: NSColor? = nil) {
    let p = NSBezierPath(roundedRect: NSRect(x:x,y:y,width:w,height:h), xRadius:18,yRadius:18)
    fill.setFill(); p.fill()
    if let border = border { border.setStroke(); p.lineWidth = 2; p.stroke() }
}
func label(_ s:String, _ x:CGFloat, _ y:CGFloat, _ w:CGFloat, _ size:CGFloat = 26, _ color:NSColor = ink, bold:Bool = false) {
    let p = NSMutableParagraphStyle(); p.lineSpacing = 7
    let font = NSFont(name: bold ? "AppleSDGothicNeo-Bold" : "AppleSDGothicNeo-Regular",size:size) ?? .systemFont(ofSize:size)
    (s as NSString).draw(in:NSRect(x:x,y:y,width:w,height:180),withAttributes:[.font:font,.foregroundColor:color,.paragraphStyle:p])
}
func arrow(_ x1:CGFloat,_ y1:CGFloat,_ x2:CGFloat,_ y2:CGFloat,_ color:NSColor = blue) {
    color.setStroke(); let p=NSBezierPath(); p.lineWidth=4
    p.move(to:NSPoint(x:x1,y:y1)); p.line(to:NSPoint(x:x2,y:y2)); p.stroke()
    let a=atan2(y2-y1,x2-x1); let q=NSBezierPath()
    q.move(to:NSPoint(x:x2,y:y2))
    q.line(to:NSPoint(x:x2-16*cos(a-0.45),y:y2-16*sin(a-0.45)))
    q.line(to:NSPoint(x:x2-16*cos(a+0.45),y:y2-16*sin(a+0.45)))
    q.close(); color.setFill(); q.fill()
}
func render(_ name:String,_ draw:()->Void) throws {
    let im=NSImage(size:NSSize(width:1600,height:1000))
    im.lockFocusFlipped(true)
    NSColor.white.setFill(); NSRect(x:0,y:0,width:1600,height:1000).fill()
    draw()
    label("B3-1 학습용 설명 그림 · 실제 AWS 콘솔 캡처 및 구축 완료 증빙이 아닙니다.",60,947,1480,20,muted)
    im.unlockFocus()
    let rep=NSBitmapImageRep(data:im.tiffRepresentation!)!
    try rep.representation(using:.png,properties:[:])!.write(to:output.appendingPathComponent(name))
}

try render("01-architecture.png") {
    label("인터넷 요청이 내 웹 서버까지 도착하는 길",60,40,1480,42,ink,bold:true)
    label("서울 리전 ap-northeast-2 · 전용 VPC 1개 · Public Subnet 1개 · EC2 1대",60,103,1480,26,muted)
    box(60,190,310,190,pale)
    label("외부 사용자",85,215,265,30,blue,bold:true)
    label("http://퍼블릭IP/health\nHTTP · TCP 80",85,270,270)
    box(60,410,310,160,pale)
    label("내 Mac",85,430,265,30,green,bold:true)
    label("개인 공인 IP /32\nSSH · TCP 22",85,485,265)
    box(455,220,255,290,NSColor(calibratedRed:1,green:0.96,blue:0.89,alpha:1),orange)
    label("Internet\nGateway",480,245,210,32,orange,bold:true)
    label("b3-1-igw\nVPC에 연결\n인터넷 출입구",480,362,210,25)
    arrow(370,280,455,280)
    arrow(370,490,455,490,green)
    box(770,185,770,690,pale,blue)
    label("VPC · b3-1-vpc",795,205,700,30,blue,bold:true)
    label("10.0.0.0/16",795,250,700,25,muted)
    box(810,305,690,365,.white,green)
    label("Public Subnet · 10.0.1.0/24",835,326,640,29,green,bold:true)
    box(845,395,620,235,NSColor(calibratedRed:0.94,green:0.98,blue:0.96,alpha:1),green)
    label("Security Group · EC2에 적용",870,414,575,26,green,bold:true)
    box(890,480,530,118,.white)
    label("EC2 · b3-1-web",912,492,480,29,ink,bold:true)
    label("퍼블릭 IPv4 → Nginx :80 → OK",912,542,480,24)
    arrow(710,365,800,365)
    box(810,705,690,135,.white)
    label("Subnet과 연결한 Route Table",835,721,640,26,blue,bold:true)
    label("10.0.0.0/16 → local    |    0.0.0.0/0 → IGW",835,770,640,24)
    label("필수 조건",60,650,650,30,ink,bold:true)
    label("① IGW 연결 + 기본 경로\n② EC2 퍼블릭 IP\n③ SG 허용 + Nginx 실행",60,702,650,28)
    label("화살표는 요청 방향입니다. 응답은 반대로 돌아옵니다.",60,882,1470,24,muted)
}

try render("02-access-rules.png") {
    label("웹 접속은 누구나, 서버 관리는 나만",60,40,1480,42,ink,bold:true)
    label("EC2 → Security Groups → b3-1-web-sg → Inbound rules",60,106,1480,26,muted)
    box(60,190,1480,390,pale)
    label("유형",90,213,280,27,muted,bold:true)
    label("프로토콜 / 포트",400,213,410,27,muted,bold:true)
    label("소스",880,213,580,27,muted,bold:true)
    box(80,273,1440,120,.white)
    label("HTTP",105,292,260,34,blue,bold:true)
    label("TCP / 80",410,294,400,32)
    label("0.0.0.0/0",890,287,600,32,blue,bold:true)
    label("Anywhere-IPv4 · 모든 외부 사용자",890,337,600,24,muted)
    box(80,420,1440,120,.white)
    label("SSH",105,441,260,34,green,bold:true)
    label("TCP / 22",410,442,400,32)
    label("내 공인 IPv4/32",890,434,600,32,green,bold:true)
    label("My IP · 현재 접속하는 내 컴퓨터의 주소",890,486,600,24,muted)
    box(60,630,715,230,NSColor(calibratedRed:0.94,green:0.98,blue:0.96,alpha:1))
    label("Security Group",85,656,655,31,green,bold:true)
    label("어느 주소에서 어느 포트로\n서버에 들어올 수 있는가?",85,714,655,29)
    box(805,630,735,230,pale)
    label("IAM",830,656,665,31,blue,bold:true)
    label("누가 AWS에서 서버와 네트워크를\n생성·수정·삭제할 수 있는가?",830,714,665,29)
    label("두 규칙만 인바운드에 추가합니다. 전체 포트 공개 규칙은 만들지 않습니다.",60,886,1480,25,muted)
}

try render("03-verification.png") {
    label("명령어를 실행하는 위치가 다릅니다",60,40,1480,42,ink,bold:true)
    label("터미널 A는 SSH 접속용, 터미널 B는 외부 접속 검증용으로 사용하세요.",60,106,1480,26,muted)
    box(60,195,710,370,pale,blue)
    label("내 Mac · 터미널 B",88,218,650,33,blue,bold:true)
    label("주소: EC2의 퍼블릭 IP",88,282,650,27)
    box(85,335,660,125,.white)
    label("curl -i --max-time 10 \\\n  http://퍼블릭IP/health",110,354,610,29)
    label("200 + OK → 외부 접속 증빙",88,495,650,29,blue,bold:true)
    box(815,195,725,370,NSColor(calibratedRed:0.94,green:0.98,blue:0.96,alpha:1),green)
    label("EC2 · SSH로 접속한 터미널 A",843,218,665,32,green,bold:true)
    label("주소: localhost (서버 자신)",843,282,665,27)
    box(840,335,675,125,.white)
    label("curl -i --max-time 10 \\\n  http://localhost/health",865,354,625,29)
    label("200 + OK → 서버 내부 실행 증빙",843,495,665,29,green,bold:true)
    label("어디에서 문제가 생겼는지 나누어 확인하기",60,620,1480,33,ink,bold:true)
    box(60,690,460,160,pale)
    label("내부도 실패",85,712,410,30,ink,bold:true)
    label("Nginx 실행·설정·80 포트",85,769,410,25)
    box(550,690,480,160,pale)
    label("내부 성공 / 외부 실패",575,712,430,30,ink,bold:true)
    label("퍼블릭 IP·SG·라우팅·IGW",575,769,430,25)
    box(1060,690,480,160,pale)
    label("둘 다 성공",1085,712,430,30,ink,bold:true)
    label("URL·200·OK를 캡처",1085,769,430,25)
    label("외부 검증은 SSH 세션 밖에서 실행해야 합니다. 예시 출력은 제출 증빙으로 사용하지 않습니다.",60,888,1480,24,muted)
}
