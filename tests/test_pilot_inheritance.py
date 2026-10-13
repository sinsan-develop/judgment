"""확정 전체 split을 상속하고 이동을 금지하는 계약 검증."""
import importlib.util
from pathlib import Path
import unittest
from unittest.mock import patch
import json
import tempfile

spec = importlib.util.spec_from_file_location('aihub_review', Path(__file__).parents[1]/'docs'/'aihub116_review.py')
review = importlib.util.module_from_spec(spec)
spec.loader.exec_module(review)


class PilotInheritanceTests(unittest.TestCase):
    def test_selected_groups_keep_full_split_even_when_ratios_are_unbalanced(self):
        groups = [[{'input_key':str(i),'schema':'business','target':(0,str(i)),
                    'utterance':str(i)}] for i in range(12)]
        full = {k:[] for k in review.SPLITS}
        full['train'] = groups[:2]
        full['calibration'] = groups[2:5]
        full['selection'] = groups[5:9]
        full['test'] = groups[9:]
        result = review.pilot_plan(groups, seed=13, full_parts=full)
        self.assertEqual([result['split'][k]['positive'] for k in review.SPLITS],[2,3,4,3])
        self.assertTrue(result['inherits_full_split'])
        self.assertEqual(len(result['group_assignment']),12)
        for assignment in result['group_assignment']:
            self.assertEqual(assignment['split'],assignment['full_split'])

    def test_missing_or_multiply_assigned_full_group_blocks_selection(self):
        group = [{'input_key':'only','schema':'business','target':(0,'label'),'utterance':'합성'}]
        parts = {k:[] for k in review.SPLITS}
        with self.assertRaisesRegex(ValueError,'full_group_assignment'):
            review.pilot_plan([group],full_parts=parts)
        parts['train'] = [group]; parts['test'] = [group]
        with self.assertRaisesRegex(ValueError,'full_group_assignment'):
            review.pilot_plan([group],full_parts=parts)

    def test_fixed_mapping_is_used_without_calling_any_splitter(self):
        rows=[dict(file=0,excel_row=i+2,schema='business',role='고객',utterance='합성'+str(i),
                   label='의도'+str(i),valid_context_block=True,qa='Q',context=(),block=(0,i)) for i in range(12)]
        baseline,full=review.analyze(rows,[])
        with patch.object(review,'balanced_parts',side_effect=AssertionError('재분할 금지')):
            result,mapping=review.analyze(rows,[],full_mapping=full)
        self.assertEqual({(r['file_index'],r['excel_row']):r for r in mapping},
                         {(r['file_index'],r['excel_row']):r for r in full})
        self.assertEqual(result['split'],baseline['split'])
        self.assertTrue(result['full_split_loaded_from_fixed_mapping'])

    def test_existing_records_are_preserved_when_writes_are_unavailable(self):
        with tempfile.TemporaryDirectory(dir=Path(__file__).parents[1]/'.work') as folder:
            path=Path(folder)/'record.json';value={'group':7,'split':'test'}
            path.write_text(json.dumps(value),encoding='utf-8');before=path.read_bytes()
            with patch.object(Path,'write_text',side_effect=OSError('disk_full')):
                review.preserve_json_record(path,value)
                with self.assertRaisesRegex(ValueError,'existing_analysis_changed'):
                    review.preserve_json_record(path,{'group':7,'split':'train'})
            self.assertEqual(path.read_bytes(),before)
