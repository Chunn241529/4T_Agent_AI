#!/bin/bash

# Kiểm tra cấu hình Git
if ! git config user.name > /dev/null || ! git config user.email > /dev/null; then
  echo "❌ Git chưa cấu hình tên hoặc email."
  echo "Vui lòng chạy:"
  echo '  git config --global user.name "vtrung836"'
  echo '  git config --global user.email "vtrung836@gmail.com"'
  exit 1
fi

# Lấy commit message
if [ -z "$1" ]; then
  echo "📝 Nhập commit message:"
  read commit_message
else
  commit_message="$1"
fi

if [ -z "$commit_message" ]; then
  echo "⚠️ Commit message không được để trống!"
  exit 1
fi

# Add file
git add .

# Commit (nếu có thay đổi)
if git diff --cached --quiet; then
  echo "⚠️ Không có thay đổi nào để commit."
else
  git commit -m "$commit_message"
fi

# Danh sách branch local
branches=($(git branch --format="%(refname:short)"))
current_branch=$(git rev-parse --abbrev-ref HEAD)

echo "🌿 Danh sách branch local:"
for i in "${!branches[@]}"; do
  if [ "${branches[$i]}" == "$current_branch" ]; then
    echo "$((i+1))) ${branches[$i]} (hiện tại)"
  else
    echo "$((i+1))) ${branches[$i]}"
  fi
done

# Hỏi chọn branch
echo "🔀 Nhập số branch muốn push (Enter = branch hiện tại, hoặc nhập tên branch mới để tạo):"
read selected

# Nếu để trống → dùng branch hiện tại
if [ -z "$selected" ]; then
  selected_branch=$current_branch
# Nếu nhập số → chọn branch theo index
elif [[ "$selected" =~ ^[0-9]+$ ]] && [ "$selected" -le "${#branches[@]}" ]; then
  selected_branch=${branches[$((selected-1))]}
# Nếu không → coi như tên branch mới
else
  selected_branch=$selected
fi

# Kiểm tra branch có tồn tại local chưa
if git show-ref --verify --quiet "refs/heads/$selected_branch"; then
  echo "✅ Dùng branch '$selected_branch'."
  git checkout "$selected_branch"
else
  echo "🌱 Branch '$selected_branch' chưa có. Tạo mới..."
  git checkout -b "$selected_branch"
fi

# Push (tạo remote branch nếu chưa có)
git push -u origin "$selected_branch"

echo "✅ Đã push lên branch '$selected_branch' với message: $commit_message"
