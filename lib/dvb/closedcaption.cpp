#include <lib/base/eerror.h>
#include <lib/dvb/closedcaption.h>
#include <lib/dvb/idemux.h>
#include <lib/gdi/gpixmap.h>

DEFINE_REF(eClosedCaptionParser);

eClosedCaptionParser::eClosedCaptionParser(iDVBDemux *demux) : m_pid(-1)
{
       eDebug("[eClosedCaptionParser] Starting!");
       setStreamID(0x06); /* private data */

       if (demux->createPESReader(eApp, m_pes_reader))
               eDebug("[eClosedCaptionParser] failed to create closed caption PES reader!");
       else {
               eDebug("[eClosedCaptionParser] created closed caption PES reader!");
               m_pes_reader->connectRead(sigc::mem_fun(*this, &eClosedCaptionParser::processData), m_read_connection);
       }
}

eClosedCaptionParser::~eClosedCaptionParser()
{
}

void eClosedCaptionParser::processPESPacket(uint8_t *pkt, int len)
{
       unsigned char *p = pkt;

       printf("[eClosedCaptionParser] PES packet len=%d\n", len);
       for (unsigned int i = 0; i < len; i++)
               printf("%02x%s", p[i], ((i + 1) % 16) ? " " : "\n");
       printf("\n");
#if 0
       p += 4; len -= 4; /* start code, already be verified by pes parser */
       p += 2; len -= 2; /* length, better use the argument */

       p += 3; len -= 3; /* pes header */

       p += 0x24; len -= 0x24; /* skip header */

       p++; len--;
#endif
}

int eClosedCaptionParser::start(int pid)
{
       eDebug("[eClosedCaptionParser] starting PES reader on pid=%04x", pid);
       if (m_pes_reader && pid >= 0 && pid < 0x1fff)
       {
               m_pid = pid;
               return m_pes_reader->start(pid);
       }
       else
               return -1;
}

