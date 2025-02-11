import os
import shutil
import tempfile
import unittest

from transformers import BertTokenizer, is_torch_available, set_seed
from transformers.testing_utils import require_torch


if is_torch_available():
    import torch

    from transformers import (
        DataCollatorForLanguageModeling,
        DataCollatorForNextSentencePrediction,
        DataCollatorForPermutationLanguageModeling,
        DataCollatorForSOP,
        DataCollatorForTokenClassification,
        DataCollatorWithPadding,
        default_data_collator,
    )


@require_torch
class DataCollatorIntegrationTest(unittest.TestCase):
    def setUp(self):
        self.tmpdirname = tempfile.mkdtemp()

        vocab_tokens = ["[UNK]", "[CLS]", "[SEP]", "[PAD]", "[MASK]"]
        self.vocab_file = os.path.join(self.tmpdirname, "vocab.txt")
        with open(self.vocab_file, "w", encoding="utf-8") as vocab_writer:
            vocab_writer.write("".join([x + "\n" for x in vocab_tokens]))

    def tearDown(self):
        shutil.rmtree(self.tmpdirname)

    def test_default_with_dict(self):
        features = [{"label": i, "inputs": [0, 1, 2, 3, 4, 5]} for i in range(8)]
        batch = default_data_collator(features)
        self.assertTrue(batch["labels"].equal(torch.tensor(list(range(8)))))
        self.assertEqual(batch["labels"].dtype, torch.long)
        self.assertEqual(batch["inputs"].shape, torch.Size([8, 6]))

        # With label_ids
        features = [{"label_ids": [0, 1, 2], "inputs": [0, 1, 2, 3, 4, 5]} for i in range(8)]
        batch = default_data_collator(features)
        self.assertTrue(batch["labels"].equal(torch.tensor([[0, 1, 2]] * 8)))
        self.assertEqual(batch["labels"].dtype, torch.long)
        self.assertEqual(batch["inputs"].shape, torch.Size([8, 6]))

        # Features can already be tensors
        features = [{"label": i, "inputs": torch.randint(10, [10])} for i in range(8)]
        batch = default_data_collator(features)
        self.assertTrue(batch["labels"].equal(torch.tensor(list(range(8)))))
        self.assertEqual(batch["labels"].dtype, torch.long)
        self.assertEqual(batch["inputs"].shape, torch.Size([8, 10]))

        # Labels can already be tensors
        features = [{"label": torch.tensor(i), "inputs": torch.randint(10, [10])} for i in range(8)]
        batch = default_data_collator(features)
        self.assertEqual(batch["labels"].dtype, torch.long)
        self.assertTrue(batch["labels"].equal(torch.tensor(list(range(8)))))
        self.assertEqual(batch["labels"].dtype, torch.long)
        self.assertEqual(batch["inputs"].shape, torch.Size([8, 10]))

    def test_default_classification_and_regression(self):
        data_collator = default_data_collator

        features = [{"input_ids": [0, 1, 2, 3, 4], "label": i} for i in range(4)]
        batch = data_collator(features)
        self.assertEqual(batch["labels"].dtype, torch.long)

        features = [{"input_ids": [0, 1, 2, 3, 4], "label": float(i)} for i in range(4)]
        batch = data_collator(features)
        self.assertEqual(batch["labels"].dtype, torch.float)

    def test_default_with_no_labels(self):
        features = [{"label": None, "inputs": [0, 1, 2, 3, 4, 5]} for i in range(8)]
        batch = default_data_collator(features)
        self.assertTrue("labels" not in batch)
        self.assertEqual(batch["inputs"].shape, torch.Size([8, 6]))

        # With label_ids
        features = [{"label_ids": None, "inputs": [0, 1, 2, 3, 4, 5]} for i in range(8)]
        batch = default_data_collator(features)
        self.assertTrue("labels" not in batch)
        self.assertEqual(batch["inputs"].shape, torch.Size([8, 6]))

    def test_data_collator_with_padding(self):
        tokenizer = BertTokenizer(self.vocab_file)
        features = [{"input_ids": [0, 1, 2]}, {"input_ids": [0, 1, 2, 3, 4, 5]}]

        data_collator = DataCollatorWithPadding(tokenizer)
        batch = data_collator(features)
        self.assertEqual(batch["input_ids"].shape, torch.Size([2, 6]))
        self.assertEqual(batch["input_ids"][0].tolist(), [0, 1, 2] + [tokenizer.pad_token_id] * 3)

        data_collator = DataCollatorWithPadding(tokenizer, padding="max_length", max_length=10)
        batch = data_collator(features)
        self.assertEqual(batch["input_ids"].shape, torch.Size([2, 10]))

        data_collator = DataCollatorWithPadding(tokenizer, pad_to_multiple_of=8)
        batch = data_collator(features)
        self.assertEqual(batch["input_ids"].shape, torch.Size([2, 8]))

    def test_data_collator_for_token_classification(self):
        tokenizer = BertTokenizer(self.vocab_file)
        features = [
            {"input_ids": [0, 1, 2], "labels": [0, 1, 2]},
            {"input_ids": [0, 1, 2, 3, 4, 5], "labels": [0, 1, 2, 3, 4, 5]},
        ]

        data_collator = DataCollatorForTokenClassification(tokenizer)
        batch = data_collator(features)
        self.assertEqual(batch["input_ids"].shape, torch.Size([2, 6]))
        self.assertEqual(batch["input_ids"][0].tolist(), [0, 1, 2] + [tokenizer.pad_token_id] * 3)
        self.assertEqual(batch["labels"].shape, torch.Size([2, 6]))
        self.assertEqual(batch["labels"][0].tolist(), [0, 1, 2] + [-100] * 3)

        data_collator = DataCollatorForTokenClassification(tokenizer, padding="max_length", max_length=10)
        batch = data_collator(features)
        self.assertEqual(batch["input_ids"].shape, torch.Size([2, 10]))
        self.assertEqual(batch["labels"].shape, torch.Size([2, 10]))

        data_collator = DataCollatorForTokenClassification(tokenizer, pad_to_multiple_of=8)
        batch = data_collator(features)
        self.assertEqual(batch["input_ids"].shape, torch.Size([2, 8]))
        self.assertEqual(batch["labels"].shape, torch.Size([2, 8]))

        data_collator = DataCollatorForTokenClassification(tokenizer, label_pad_token_id=-1)
        batch = data_collator(features)
        self.assertEqual(batch["input_ids"].shape, torch.Size([2, 6]))
        self.assertEqual(batch["input_ids"][0].tolist(), [0, 1, 2] + [tokenizer.pad_token_id] * 3)
        self.assertEqual(batch["labels"].shape, torch.Size([2, 6]))
        self.assertEqual(batch["labels"][0].tolist(), [0, 1, 2] + [-1] * 3)

    def test_data_collator_for_language_modeling(self):
        tokenizer = BertTokenizer(self.vocab_file)
        no_pad_features = [{"input_ids": list(range(10))}, {"input_ids": list(range(10))}]
        pad_features = [{"input_ids": list(range(5))}, {"input_ids": list(range(10))}]

        data_collator = DataCollatorForLanguageModeling(tokenizer, mlm=False)
        batch = data_collator(no_pad_features)
        self.assertEqual(batch["input_ids"].shape, torch.Size((2, 10)))
        self.assertEqual(batch["labels"].shape, torch.Size((2, 10)))

        batch = data_collator(pad_features)
        self.assertEqual(batch["input_ids"].shape, torch.Size((2, 10)))
        self.assertEqual(batch["labels"].shape, torch.Size((2, 10)))

        tokenizer._pad_token = None
        data_collator = DataCollatorForLanguageModeling(tokenizer, mlm=False)
        with self.assertRaises(ValueError):
            # Expect error due to padding token missing
            data_collator(pad_features)

        set_seed(42)  # For reproducibility
        tokenizer = BertTokenizer(self.vocab_file)
        data_collator = DataCollatorForLanguageModeling(tokenizer)
        batch = data_collator(no_pad_features)
        self.assertEqual(batch["input_ids"].shape, torch.Size((2, 10)))
        self.assertEqual(batch["labels"].shape, torch.Size((2, 10)))

        masked_tokens = batch["input_ids"] == tokenizer.mask_token_id
        self.assertTrue(torch.any(masked_tokens))
        self.assertTrue(all(x == -100 for x in batch["labels"][~masked_tokens].tolist()))

        batch = data_collator(pad_features)
        self.assertEqual(batch["input_ids"].shape, torch.Size((2, 10)))
        self.assertEqual(batch["labels"].shape, torch.Size((2, 10)))

        masked_tokens = batch["input_ids"] == tokenizer.mask_token_id
        self.assertTrue(torch.any(masked_tokens))
        self.assertTrue(all(x == -100 for x in batch["labels"][~masked_tokens].tolist()))

    def test_plm(self):
        tokenizer = BertTokenizer(self.vocab_file)
        no_pad_features = [{"input_ids": list(range(10))}, {"input_ids": list(range(10))}]
        pad_features = [{"input_ids": list(range(5))}, {"input_ids": list(range(10))}]

        data_collator = DataCollatorForPermutationLanguageModeling(tokenizer)

        batch = data_collator(pad_features)
        self.assertIsInstance(batch, dict)
        self.assertEqual(batch["input_ids"].shape, torch.Size((2, 10)))
        self.assertEqual(batch["perm_mask"].shape, torch.Size((2, 10, 10)))
        self.assertEqual(batch["target_mapping"].shape, torch.Size((2, 10, 10)))
        self.assertEqual(batch["labels"].shape, torch.Size((2, 10)))

        batch = data_collator(no_pad_features)
        self.assertIsInstance(batch, dict)
        self.assertEqual(batch["input_ids"].shape, torch.Size((2, 10)))
        self.assertEqual(batch["perm_mask"].shape, torch.Size((2, 10, 10)))
        self.assertEqual(batch["target_mapping"].shape, torch.Size((2, 10, 10)))
        self.assertEqual(batch["labels"].shape, torch.Size((2, 10)))

        example = [torch.randint(5, [5])]
        with self.assertRaises(ValueError):
            # Expect error due to odd sequence length
            data_collator(example)

    def test_nsp(self):
        tokenizer = BertTokenizer(self.vocab_file)
        features = [{"tokens_a": [0, 1, 2, 3, 4], "tokens_b": [0, 1, 2, 3, 4], "is_random_next": i} for i in range(2)]
        data_collator = DataCollatorForNextSentencePrediction(tokenizer)
        batch = data_collator(features)

        self.assertEqual(batch["input_ids"].shape, torch.Size((2, 512)))
        self.assertEqual(batch["token_type_ids"].shape, torch.Size((2, 512)))
        self.assertEqual(batch["labels"].shape, torch.Size((2, 512)))
        self.assertEqual(batch["next_sentence_label"].shape, torch.Size((2,)))

    def test_sop(self):
        tokenizer = BertTokenizer(self.vocab_file)
        features = [
            {
                "input_ids": torch.tensor([0, 1, 2, 3, 4]),
                "token_type_ids": torch.tensor([0, 1, 2, 3, 4]),
                "sentence_order_label": torch.tensor(i),
            }
            for i in range(2)
        ]
        data_collator = DataCollatorForSOP(tokenizer)
        batch = data_collator(features)

        self.assertEqual(batch["input_ids"].shape, torch.Size((2, 5)))
        self.assertEqual(batch["token_type_ids"].shape, torch.Size((2, 5)))
        self.assertEqual(batch["labels"].shape, torch.Size((2, 5)))
        self.assertEqual(batch["sentence_order_label"].shape, torch.Size((2,)))
