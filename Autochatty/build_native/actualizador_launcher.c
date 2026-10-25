/* Windows x64 minimalist PE launcher, with no CRT. Companion script required.
 * It does NOT auto-elevate, download software, or touch ChatGPT itself.
 */
typedef unsigned short W;
typedef unsigned long DWORD;
typedef void *HANDLE;
__declspec(dllimport) DWORD GetModuleFileNameW(HANDLE, W *, DWORD);
__declspec(dllimport) void ExitProcess(unsigned int);
__declspec(dllimport) void *ShellExecuteW(void*,const W*,const W*,const W*,const W*,int);
__declspec(dllimport) int MessageBoxW(void*,const W*,const W*,unsigned int);
static int append(W *buf, int n, int max, const W *s) {
    int j=0;
    while(s[j]) { if(n>=max-1) return -1; buf[n++]=s[j++]; }
    buf[n]=0;
    return n;
}
void entry(void) {
    static W source[32768]; static W args[32768];
    const W suffix[]=L"actualizador.ps1";
    const W prefix[]=L"-NoProfile -STA -ExecutionPolicy Bypass -File \"";
    DWORD n=GetModuleFileNameW((HANDLE)0,source,32768);
    int i=(int)n;
    if(!n || n>=32000) goto error;
    while(i>0 && source[i-1]!=L'\\' && source[i-1]!=L'/') i--;
    if(i==0 || append(source,i,32768,suffix)<0) goto error;
    int k=append(args,0,32768,prefix);
    if(k<0 || (k=append(args,k,32768,source))<0 || (k=append(args,k,32768,L"\""))<0) goto error;
    {
        void *ret=ShellExecuteW((void*)0,L"open",L"powershell.exe",args,(void*)0,1);
        if((unsigned long long)ret>32) ExitProcess(0);
    }
error:
    MessageBoxW((void*)0,L"No se pudo iniciar actualizador.ps1. Mantenga el EXE junto al script y verifique Windows PowerShell.",L"Actualizador ChatGPT - Error",0x10);
    ExitProcess(1);
}
