path = r'c:\Users\anita\OneDrive\Desktop\New folder (2)\attendance_system\templates\base.html'
with open(path, encoding='utf-8') as f:
    content = f.read()

# Keep only up to and including the FIRST </html>
marker = '</html>'
idx = content.find(marker)
if idx == -1:
    print('ERROR: </html> not found!')
else:
    fixed = content[:idx + len(marker)] + '\n'
    with open(path, 'w', encoding='utf-8') as f:
        f.write(fixed)
    print(f'Fixed! Truncated at position {idx}. File saved.')
    print('Now run: python app.py')
