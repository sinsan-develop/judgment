"""평가의 원래 collate·padding·점수 함수를 보존하는 GPU micro-forward."""
from contextlib import contextmanager
from .contracts import ConfigError


@contextmanager
def bounded_evaluation_forward(module):
    original=module._forward
    def forward(model,batch,device,amp,detach_encoder):
        import torch
        if torch.is_grad_enabled():raise ConfigError('evaluation_requires_no_grad')
        size=batch['input_ids'].shape[0]
        if any(not ((isinstance(v,torch.Tensor) and v.ndim>0 and v.shape[0]==size) or
                    (isinstance(v,list) and len(v)==size)) for v in batch.values()):
            raise ConfigError('evaluation_batch_structure')
        results=[]
        for index in range(size):
            micro={key:value[index:index+1] for key,value in batch.items()}
            logits=original(model,micro,device,amp=amp,detach_encoder=detach_encoder)
            results.append(logits.detach().cpu());del logits
        return torch.cat(results,dim=0)
    module._forward=forward
    try:yield
    finally:module._forward=original
