import Editor from '@monaco-editor/react';

const LANG_MAP = {
  python: 'python',
  node: 'javascript',
  bash: 'shell',
  powershell: 'powershell',
};

export default function CodeEditor({ code, language, onChange }) {
  return (
    <div className="editor-wrapper">
      <Editor
        height="100%"
        language={LANG_MAP[language] || 'plaintext'}
        value={code}
        onChange={(val) => onChange(val || '')}
        theme="vs-dark"
        options={{
          fontSize: 14,
          fontFamily: "'JetBrains Mono', 'Fira Code', 'Consolas', monospace",
          minimap: { enabled: false },
          scrollBeyondLastLine: false,
          padding: { top: 16, bottom: 16 },
          lineNumbers: 'on',
          roundedSelection: true,
          cursorBlinking: 'smooth',
          cursorSmoothCaretAnimation: 'on',
          smoothScrolling: true,
          wordWrap: 'on',
          automaticLayout: true,
          renderLineHighlight: 'gutter',
          scrollbar: {
            verticalScrollbarSize: 8,
            horizontalScrollbarSize: 8,
          },
        }}
      />
    </div>
  );
}
