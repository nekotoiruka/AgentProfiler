"""進捗率計算ユーティリティ

セッション内の回答進捗を整数パーセンテージで計算する。
"""


def calculate_progress(answered: int, total: int) -> int:
  """進捗率を整数%で計算する（切り捨て）

  Args:
      answered: 回答済み質問数
      total: 全質問数 (> 0)

  Returns:
      0-100 の整数
  """
  if total <= 0:
    return 0
  return int(answered / total * 100)
