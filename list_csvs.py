import os
darglobal_dir = 'data/raw/darglobal'
if os.path.exists(darglobal_dir):
    for f in sorted(os.listdir(darglobal_dir)):
        if f.endswith('.csv'):
            full = os.path.join(darglobal_dir, f)
            print(f'FILE: {f}')
            with open(full, 'r', encoding='utf-8-sig') as fh:
                content = fh.read()
                print(f'  Content preview: {content[:200]}')
            print()
else:
    print('Directory does not exist')