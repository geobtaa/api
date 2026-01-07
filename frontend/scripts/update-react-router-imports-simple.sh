#!/bin/bash

# Simple bash script to bulk-update imports from react-router-dom to react-router
# This is a non-interactive version that directly updates files

echo "🔄 Updating imports from react-router-dom to react-router..."

# Find and replace in all TypeScript/JavaScript files
find frontend/src frontend/app -type f \( -name "*.ts" -o -name "*.tsx" -o -name "*.js" -o -name "*.jsx" \) \
  -exec sed -i '' "s/'react-router-dom'/'react-router'/g" {} \; \
  -exec sed -i '' 's/"react-router-dom"/"react-router"/g' {} \;

echo "✅ Done! All imports have been updated."
echo ""
echo "📋 Summary:"
echo "  - Replaced 'react-router-dom' with 'react-router'"
echo "  - Updated both single and double quote imports"
echo ""
echo "⚠️  Note: Please review the changes and test your application."
