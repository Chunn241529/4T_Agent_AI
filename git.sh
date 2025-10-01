#!/bin/bash

# ====== Hàm tiện ích ======
check_git_config() {
  if ! git config user.name > /dev/null || ! git config user.email > /dev/null; then
    echo "❌ Git chưa cấu hình tên hoặc email."
    echo "Vui lòng chạy:"
    echo '  git config --global user.name "vtrung836"'
    echo '  git config --global user.email "vtrung836@gmail.com"'
    exit 1
  fi
}

check_branch() {
  echo "🌿 Branch hiện tại: $(git rev-parse --abbrev-ref HEAD)"
  echo "📌 Danh sách branch local:"
  git branch
}

check_commit() {
  echo "📜 Commit gần nhất:"
  git log -1 --pretty=format:"%h - %s (%ci) [tác giả: %an]"
}

check_out() {
  # Nếu có tham số thì checkout luôn
  if [ -n "$2" ]; then
    target_branch="$2"
  else
    # Nếu không có tham số thì hiện menu chọn nhánh
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

    echo "🔀 Nhập số branch muốn checkout (hoặc nhập tên branch mới):"
    read selected

    if [[ -z "$selected" ]]; then
      echo "⚠️ Bạn chưa chọn branch nào."
      exit 1
    elif [[ "$selected" =~ ^[0-9]+$ ]] && [ "$selected" -le "${#branches[@]}" ]; then
      target_branch=${branches[$((selected-1))]}
    else
      target_branch=$selected
    fi
  fi

  # Checkout hoặc tạo mới
  if git show-ref --verify --quiet "refs/heads/$target_branch"; then
    echo "✅ Chuyển sang branch '$target_branch'."
    git checkout "$target_branch"
  else
    echo "🌱 Branch '$target_branch' chưa có. Tạo mới..."
    git checkout -b "$target_branch"
  fi
}

push_code() {
  check_git_config

  # Lấy commit message
  if [ -z "$2" ]; then
    echo "📝 Nhập commit message:"
    read commit_message
  else
    commit_message="$2"
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

  echo "🔀 Nhập số branch muốn push (Enter = branch hiện tại, hoặc nhập tên branch mới để tạo):"
  read selected

  if [ -z "$selected" ]; then
    selected_branch=$current_branch
  elif [[ "$selected" =~ ^[0-9]+$ ]] && [ "$selected" -le "${#branches[@]}" ]; then
    selected_branch=${branches[$((selected-1))]}
  else
    selected_branch=$selected
  fi

  # Kiểm tra branch local
  if git show-ref --verify --quiet "refs/heads/$selected_branch"; then
    echo "✅ Dùng branch '$selected_branch'."
    git checkout "$selected_branch"
  else
    echo "🌱 Branch '$selected_branch' chưa có. Tạo mới..."
    git checkout -b "$selected_branch"
  fi

  git push -u origin "$selected_branch"

  echo "✅ Đã push lên branch '$selected_branch' với message: $commit_message"
}

merge_to() {
  check_git_config
  current_branch=$(git rev-parse --abbrev-ref HEAD)

  # Nếu có tham số thì dùng làm nhánh đích
  if [ -n "$2" ]; then
    target_branch="$2"
  else
    # Nếu không có tham số thì hiện menu chọn nhánh đích
    branches=($(git branch --format="%(refname:short)"))
    echo "🌿 Danh sách branch local:"
    for i in "${!branches[@]}"; do
      echo "$((i+1))) ${branches[$i]}"
    done
    echo "🔀 Nhập số branch đích (Enter = main):"
    read selected

    if [ -z "$selected" ]; then
      target_branch="main"
    elif [[ "$selected" =~ ^[0-9]+$ ]] && [ "$selected" -le "${#branches[@]}" ]; then
      target_branch=${branches[$((selected-1))]}
    else
      target_branch=$selected
    fi
  fi

  if [ "$current_branch" == "$target_branch" ]; then
    echo "⚠️ Không thể merge branch '$current_branch' vào chính nó."
    exit 1
  fi

  echo "🔄 Đang merge branch '$current_branch' vào '$target_branch'..."

  # Checkout branch đích và update
  git checkout "$target_branch" || exit 1
  git pull origin "$target_branch"

  # Merge branch hiện tại
  git merge --no-ff "$current_branch"

  if [ $? -eq 0 ]; then
    git push origin "$target_branch"
    echo "✅ Đã merge '$current_branch' vào '$target_branch' và push thành công."
  else
    echo "❌ Merge thất bại. Vui lòng xử lý conflict thủ công."
  fi
}

# ====== Router CLI ======
case "$1" in
  check_branch)
    check_branch
    ;;
  check_commit)
    check_commit
    ;;
  check_out)
    check_out "$@"
    ;;
  push)
    push_code "$@"
    ;;
  merge_to)
    merge_to "$@"
    ;;
  *)
    echo "⚙️ Cách dùng:"
    echo "  ./git.sh check_branch        # Hiện branch hiện tại và danh sách branch"
    echo "  ./git.sh check_commit        # Hiện commit gần nhất"
    echo "  ./git.sh check_out [branch]  # Checkout branch (nếu chưa có thì tạo mới)"
    echo "  ./git.sh push \"msg\"          # Commit & push với message"
    echo "  ./git.sh merge_to [branch]   # Merge branch hiện tại vào branch đích (mặc định main)"
    ;;
esac
