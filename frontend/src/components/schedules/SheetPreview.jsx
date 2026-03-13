import { useState, useCallback } from 'react';
import { X, Save, RotateCcw, Loader2 } from 'lucide-react';
import useGoogleStore from '../../store/googleStore';
import { toast } from '../../store/toastStore';

/**
 * 열 인덱스(0-based) → A1 표기법 열 문자 변환
 * 0→A, 1→B, ... 25→Z, 26→AA
 */
function colToLetter(col) {
  let letter = '';
  let c = col;
  while (c >= 0) {
    letter = String.fromCharCode((c % 26) + 65) + letter;
    c = Math.floor(c / 26) - 1;
  }
  return letter;
}

/**
 * (rowIdx, colIdx) → "B3" 형태의 A1 표기법
 * rowIdx, colIdx 모두 0-based (데이터 행 기준, 헤더 제외)
 */
function toA1(rowIdx, colIdx) {
  return `${colToLetter(colIdx)}${rowIdx + 1}`;
}

export default function SheetPreview({ spreadsheetId, onClose }) {
  const {
    sheetPreview,
    sheetPreviewLoading,
    sheetPreviewError,
    fetchSheetPreview,
    updateSheetData,
    clearSheetPreview,
  } = useGoogleStore();

  const [activeTab, setActiveTab] = useState(null);
  const [editedCells, setEditedCells] = useState(new Map());
  const [editingCell, setEditingCell] = useState(null); // { row, col }
  const [saving, setSaving] = useState(false);

  // 초기 로드
  const loadTab = useCallback(async (tabName) => {
    setActiveTab(tabName);
    setEditedCells(new Map());
    setEditingCell(null);
    try {
      await fetchSheetPreview(spreadsheetId, tabName);
    } catch {
      // error handled in store
    }
  }, [spreadsheetId, fetchSheetPreview]);

  // 첫 로드
  useState(() => {
    loadTab('Sheet1');
  });

  const values = sheetPreview?.values || [];
  const tabs = sheetPreview?.tabs || [];
  const headerRow = values[0] || [];
  const dataRows = values.slice(1);

  // 셀 클릭 → 편집 모드
  const handleCellClick = (rowIdx, colIdx) => {
    // 헤더 행 편집 불가
    if (rowIdx < 0) return;
    setEditingCell({ row: rowIdx, col: colIdx });
  };

  // 셀 값 변경
  const handleCellChange = (rowIdx, colIdx, newValue) => {
    const key = `${rowIdx}:${colIdx}`;
    const originalValue = dataRows[rowIdx]?.[colIdx] || '';
    const updated = new Map(editedCells);

    if (newValue === originalValue) {
      updated.delete(key);
    } else {
      updated.set(key, { rowIdx, colIdx, value: newValue });
    }
    setEditedCells(updated);
  };

  // 편집 완료 (blur / Enter)
  const handleCellBlur = () => {
    setEditingCell(null);
  };

  // 셀 표시 값 (편집된 값 우선)
  const getCellValue = (rowIdx, colIdx) => {
    const key = `${rowIdx}:${colIdx}`;
    if (editedCells.has(key)) {
      return editedCells.get(key).value;
    }
    return dataRows[rowIdx]?.[colIdx] || '';
  };

  // 저장
  const handleSave = async () => {
    if (editedCells.size === 0) return;
    setSaving(true);
    try {
      const updates = [];
      for (const [, edit] of editedCells) {
        // +2: 1 for 0→1 index, 1 for header row
        const cell = toA1(edit.rowIdx + 1, edit.colIdx);
        updates.push({ cell, value: edit.value });
      }
      await updateSheetData(spreadsheetId, activeTab || 'Sheet1', updates);
      toast.success(`${updates.length}개 셀이 저장되었습니다.`);
      setEditedCells(new Map());
      setEditingCell(null);
      // 새로고침
      await fetchSheetPreview(spreadsheetId, activeTab || 'Sheet1');
    } catch {
      toast.error('저장에 실패했습니다.');
    } finally {
      setSaving(false);
    }
  };

  // 취소
  const handleCancel = () => {
    setEditedCells(new Map());
    setEditingCell(null);
  };

  // 닫기
  const handleClose = () => {
    clearSheetPreview();
    setEditedCells(new Map());
    setEditingCell(null);
    onClose?.();
  };

  return (
    <div className="mt-2 border border-neutral-divider rounded-lg overflow-hidden bg-surface-base">
      {/* 상단 바: 탭 + 버튼 */}
      <div className="flex items-center justify-between px-3 py-2 bg-surface-hover border-b border-neutral-divider">
        <div className="flex items-center gap-1">
          {tabs.map((tab) => (
            <button
              key={tab}
              onClick={() => loadTab(tab)}
              className={`text-xs px-3 py-1.5 rounded font-medium transition ${
                (activeTab || 'Sheet1') === tab
                  ? 'bg-primary-600 text-white'
                  : 'text-neutral-muted hover:bg-surface-base'
              }`}
            >
              {tab}
            </button>
          ))}
        </div>
        <div className="flex items-center gap-1.5">
          {editedCells.size > 0 && (
            <>
              <button
                onClick={handleCancel}
                className="text-xs px-2.5 py-1.5 rounded border border-neutral-divider text-neutral-muted hover:bg-surface-base transition flex items-center gap-1"
              >
                <RotateCcw size={12} />
                취소
              </button>
              <button
                onClick={handleSave}
                disabled={saving}
                className="text-xs px-2.5 py-1.5 rounded bg-primary-600 text-white hover:bg-primary-700 transition flex items-center gap-1 disabled:opacity-50"
              >
                {saving ? <Loader2 size={12} className="animate-spin" /> : <Save size={12} />}
                저장 ({editedCells.size})
              </button>
            </>
          )}
          <button
            onClick={handleClose}
            className="p-1 rounded hover:bg-surface-base text-neutral-muted transition"
          >
            <X size={14} />
          </button>
        </div>
      </div>

      {/* 로딩 */}
      {sheetPreviewLoading && (
        <div className="flex items-center justify-center py-8">
          <Loader2 size={20} className="animate-spin text-primary-600" />
          <span className="ml-2 text-sm text-neutral-muted">데이터 로딩 중...</span>
        </div>
      )}

      {/* 에러 */}
      {sheetPreviewError && (
        <div className="px-3 py-4 text-center">
          <p className="text-sm text-error">{sheetPreviewError}</p>
        </div>
      )}

      {/* 테이블 */}
      {!sheetPreviewLoading && !sheetPreviewError && values.length > 0 && (
        <div className="overflow-auto max-h-[400px]">
          <table className="w-full text-xs border-collapse">
            <thead className="sticky top-0 z-10">
              <tr>
                {headerRow.map((header, colIdx) => (
                  <th
                    key={colIdx}
                    className="px-2.5 py-2 text-left font-semibold bg-neutral-100 dark:bg-neutral-800 text-neutral-main border-b border-r border-neutral-divider whitespace-nowrap"
                  >
                    {header}
                  </th>
                ))}
              </tr>
            </thead>
            <tbody>
              {dataRows.map((row, rowIdx) => (
                <tr key={rowIdx} className="hover:bg-surface-hover transition-colors">
                  {headerRow.map((_, colIdx) => {
                    const isEditing = editingCell?.row === rowIdx && editingCell?.col === colIdx;
                    const isEdited = editedCells.has(`${rowIdx}:${colIdx}`);
                    const cellValue = getCellValue(rowIdx, colIdx);

                    return (
                      <td
                        key={colIdx}
                        onClick={() => handleCellClick(rowIdx, colIdx)}
                        className={`px-2.5 py-1.5 border-b border-r border-neutral-divider cursor-pointer transition-colors ${
                          isEdited ? 'bg-amber-50 dark:bg-amber-900/20' : ''
                        }`}
                      >
                        {isEditing ? (
                          <input
                            type="text"
                            defaultValue={cellValue}
                            autoFocus
                            onBlur={(e) => {
                              handleCellChange(rowIdx, colIdx, e.target.value);
                              handleCellBlur();
                            }}
                            onKeyDown={(e) => {
                              if (e.key === 'Enter') {
                                handleCellChange(rowIdx, colIdx, e.target.value);
                                handleCellBlur();
                              }
                              if (e.key === 'Escape') {
                                handleCellBlur();
                              }
                            }}
                            className="w-full px-1 py-0.5 text-xs border border-primary-400 rounded outline-none bg-white dark:bg-neutral-900"
                          />
                        ) : (
                          <span className="text-neutral-main whitespace-nowrap">
                            {cellValue}
                          </span>
                        )}
                      </td>
                    );
                  })}
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}

      {/* 빈 데이터 */}
      {!sheetPreviewLoading && !sheetPreviewError && values.length === 0 && (
        <div className="px-3 py-6 text-center">
          <p className="text-sm text-neutral-muted">데이터가 없습니다</p>
        </div>
      )}
    </div>
  );
}
