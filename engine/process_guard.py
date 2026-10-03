"""Python audit-hook policy; not a kernel sandbox or host-wide observer."""
import os,sys
from pathlib import Path

class ProcessGuard:
    def __init__(self,unit,output,allowed_inputs):
        self.unit=Path(unit).resolve();self.output=Path(output).resolve()
        self.runtime=Path(sys.base_prefix).resolve()
        self.inputs={str(Path(p).resolve()).casefold() for p in allowed_inputs}
        self.counts={'open_events':0,'denied_open':0,'network_attempts':0,'process_attempts':0}
    @staticmethod
    def forbidden_process(event):
        return event in ('subprocess.Popen','os.system','os.posix_spawn','os.exec','os.spawn') or event.startswith('os.startfile')
    def hook(self,event,args):
        if self.forbidden_process(event):
            self.counts['process_attempts']+=1;raise PermissionError('PROCESS_BLOCKED')
        if event.startswith('socket.') and event not in ('socket.__new__','socket.gethostname'):
            self.counts['network_attempts']+=1;raise PermissionError('NETWORK_BLOCKED')
        if event=='open' and not isinstance(args[0],int):
            self.counts['open_events']+=1;p=Path(os.fsdecode(args[0])).resolve()
            mode=args[1] if isinstance(args[1],str) else '';flags=args[2] if isinstance(args[2],int) else 0
            writing=any(c in mode for c in 'wax+') or bool(flags&(os.O_WRONLY|os.O_RDWR|os.O_CREAT|os.O_TRUNC))
            allowed=p.is_relative_to(self.output) if writing else (any(p.is_relative_to(q) for q in (self.unit,self.output,self.runtime)) or str(p).casefold() in self.inputs)
            if not allowed:self.counts['denied_open']+=1;raise PermissionError('FILE_BOUNDARY')
    def report(self):
        return {'scope':'THIS_PROCESS_AFTER_HOOK_INSTALLATION','counts':dict(self.counts),
                'os_startfile_blocked':True,'os_startfile_2_blocked':True,
                'limitations':'Python open/socket/process events only, no OS-wide/RSS/native-file-operation guarantee'}
