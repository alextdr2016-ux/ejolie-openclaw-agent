import { exec } from 'child_process';
import { promisify } from 'util';
import * as path from 'path';

const execAsync = promisify(exec);

interface SalesReportParams {
  startDate: string;
  endDate: string;
  statusId?: number;
}

// Map month names to dates
const monthMap: { [key: string]: { start: string; end: string } } = {
  'ianuarie': { start: '01-01-2026', end: '31-01-2026' },
  'februarie': { start: '01-02-2026', end: '28-02-2026' },
  'martie': { start: '01-03-2026', end: '31-03-2026' },
  'aprilie': { start: '01-04-2026', end: '30-04-2026' },
  'mai': { start: '01-05-2026', end: '31-05-2026' },
  'iunie': { start: '01-06-2026', end: '30-06-2026' },
  'iulie': { start: '01-07-2026', end: '31-07-2026' },
  'august': { start: '01-08-2026', end: '31-08-2026' },
  'septembrie': { start: '01-09-2026', end: '30-09-2026' },
  'octombrie': { start: '01-10-2026', end: '31-10-2026' },
  'noiembrie': { start: '01-11-2026', end: '30-11-2026' },
  'decembrie': { start: '01-12-2026', end: '31-12-2026' }
};

// Status IDs
const statusMap: { [key: string]: number } = {
  'incasate': 14,
  'returnate': 9,
  'refuzate': 38,
  'schimb': 37
};

/**
 * Parse user message to extract report parameters
 */
function parseMessage(message: string): SalesReportParams | null {
  const lowerMsg = message.toLowerCase();
  
  // Check for status filter
  let statusId: number | undefined;
  for (const [keyword, id] of Object.entries(statusMap)) {
    if (lowerMsg.includes(keyword)) {
      statusId = id;
      break;
    }
  }
  
  // Check for "azi" (today)
  if (lowerMsg.includes('azi')) {
    const today = new Date();
    const dateStr = formatDate(today);
    return { startDate: dateStr, endDate: dateStr, statusId };
  }
  
  // Check for "luna asta" (this month)
  if (lowerMsg.includes('luna asta') || lowerMsg.includes('luna aceasta')) {
    const today = new Date();
    const year = today.getFullYear();
    const month = today.getMonth() + 1;
    const startDate = `01-${month.toString().padStart(2, '0')}-${year}`;
    const lastDay = new Date(year, month, 0).getDate();
    const endDate = `${lastDay}-${month.toString().padStart(2, '0')}-${year}`;
    return { startDate, endDate, statusId };
  }
  
  // Check for month names
  for (const [monthName, dates] of Object.entries(monthMap)) {
    if (lowerMsg.includes(monthName)) {
      return { startDate: dates.start, endDate: dates.end, statusId };
    }
  }
  
  // Check for explicit date range (DD-MM-YYYY DD-MM-YYYY)
  const dateRangeMatch = lowerMsg.match(/(\d{2}-\d{2}-\d{4})\s+(\d{2}-\d{2}-\d{4})/);
  if (dateRangeMatch) {
    return { startDate: dateRangeMatch[1], endDate: dateRangeMatch[2], statusId };
  }
  
  return null;
}

/**
 * Format date as DD-MM-YYYY
 */
function formatDate(date: Date): string {
  const day = date.getDate().toString().padStart(2, '0');
  const month = (date.getMonth() + 1).toString().padStart(2, '0');
  const year = date.getFullYear();
  return `${day}-${month}-${year}`;
}

/**
 * Execute Python sales report script
 */
async function generateReport(params: SalesReportParams): Promise<string> {
  const scriptPath = path.join(__dirname, '../../scripts/cli.py');
  const venvPython = path.join(__dirname, '../../venv/bin/python3');
  
  let command = `${venvPython} ${scriptPath} sales ${params.startDate} ${params.endDate}`;
  
  if (params.statusId) {
    command += ` --status ${params.statusId}`;
  }
  
  try {
    const { stdout, stderr } = await execAsync(command, {
      cwd: path.join(__dirname, '../..')
    });
    
    if (stderr && !stderr.includes('DEBUG:')) {
      console.error('Python stderr:', stderr);
    }
    
    // Filter out DEBUG lines
    const output = stdout.split('\n')
      .filter(line => !line.includes('DEBUG:'))
      .join('\n')
      .trim();
    
    return output || '❌ Nu s-a putut genera raportul';
  } catch (error: any) {
    console.error('Error executing Python script:', error);
    return `❌ Eroare la generarea raportului: ${error.message}`;
  }
}

/**
 * Main skill handler
 */
export async function handler(message: string): Promise<string> {
  // Check if message is a sales report request
  if (!message.toLowerCase().includes('raport') || !message.toLowerCase().includes('vânzări')) {
    return '❓ Comanda necunoscută. Încearcă:\n' +
           '• raport vânzări azi\n' +
           '• raport vânzări luna asta\n' +
           '• raport vânzări ianuarie\n' +
           '• raport incasate ianuarie\n' +
           '• raport returnate ianuarie';
  }
  
  const params = parseMessage(message);
  
  if (!params) {
    return '❌ Nu am înțeles perioada. Exemple:\n' +
           '• raport vânzări azi\n' +
           '• raport vânzări luna asta\n' +
           '• raport vânzări ianuarie\n' +
           '• raport incasate ianuarie';
  }
  
  return await generateReport(params);
}

// Export for OpenClaw
export default handler;