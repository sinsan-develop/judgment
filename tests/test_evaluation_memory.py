import types
import unittest
import importlib.util
from judgment.evaluation_memory import bounded_evaluation_forward

@unittest.skipUnless(importlib.util.find_spec('torch'),'CPU 합성 텐서 시험에는 Torch 필요')
class EvaluationMemoryTests(unittest.TestCase):
    def test_preserves_padded_input_scores_cpu_output_and_restores_training_forward(self):
        import torch
        seen=[]
        def forward(model,batch,device,amp,detach_encoder):
            seen.append((batch['input_ids'].clone(),amp,detach_encoder))
            return batch['input_ids'].float().sum(1,keepdim=True)
        module=types.SimpleNamespace(_forward=forward)
        batch={'input_ids':torch.arange(32).reshape(4,8),'attention_mask':torch.ones(4,8),'meta':[{'index':i} for i in range(4)]}
        expected=forward(None,batch,'cpu',False,False);seen.clear()
        with torch.no_grad(),bounded_evaluation_forward(module):
            actual=module._forward(None,batch,'cpu',False,False)
        self.assertTrue(torch.equal(actual,expected));self.assertEqual(actual.device.type,'cpu')
        self.assertEqual([x[0].shape for x in seen],[torch.Size([1,8])]*4)
        self.assertTrue(torch.equal(torch.cat([x[0] for x in seen]),batch['input_ids']))
        self.assertTrue(all(not x[1] and not x[2] for x in seen));self.assertIs(module._forward,forward)
    def test_exception_restores_original_forward(self):
        import torch
        def fail(*args,**kwargs):raise RuntimeError('synthetic')
        module=types.SimpleNamespace(_forward=fail)
        with self.assertRaises(RuntimeError),torch.no_grad(),bounded_evaluation_forward(module):
            module._forward(None,{'input_ids':torch.ones(2,3)},'cpu',False,False)
        self.assertIs(module._forward,fail)
