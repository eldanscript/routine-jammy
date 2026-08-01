// Supabase 연결 정보.
// publishable 키는 클라이언트에 노출되는 것을 전제로 설계된 키다 — 커밋해도 된다.
// 실제 접근 통제는 DB의 Row Level Security가 서버에서 한다.
// 사람별 쓰기 토큰은 여기 두지 않는다 — URL의 ?t= 로 전달된다.
window.ROUTINE_CONFIG = {
  supabaseUrl: 'https://wkumpxccryqjkgdhwjyb.supabase.co',
  publishableKey: 'sb_publishable_sCgRLsZ5rhY32D8dJj3PKw_GPG7gyfO',
};
