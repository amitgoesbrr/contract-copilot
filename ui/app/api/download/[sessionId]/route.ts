import { NextRequest, NextResponse } from 'next/server';

const API_URL = process.env.NEXT_PUBLIC_API_URL || 'http://localhost:8000';

export async function GET(
    request: NextRequest,
    { params }: { params: Promise<{ sessionId: string }> }
) {
    const sessionId = (await params).sessionId;

    if (!sessionId) {
        return new NextResponse('Session ID required', { status: 400 });
    }

    try {
        const backendUrl = `${API_URL}/sessions/${sessionId}/file`;
        const response = await fetch(backendUrl);

        if (!response.ok) {
            return new NextResponse(`Failed to fetch file: ${response.statusText}`, { status: response.status });
        }

        const headers = new Headers();
        headers.set('Content-Type', response.headers.get('Content-Type') || 'application/octet-stream');
        headers.set('Content-Disposition', response.headers.get('Content-Disposition') || `attachment; filename="contract_${sessionId}.pdf"`);
        headers.set('Content-Length', response.headers.get('Content-Length') || '');

        return new NextResponse(response.body, {
            status: 200,
            headers,
        });
    } catch (error) {
        console.error('Download proxy error:', error);
        return new NextResponse('Internal Server Error', { status: 500 });
    }
}
