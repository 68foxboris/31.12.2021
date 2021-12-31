#ifndef __lib_dvb_closedcaption_h
#define __lib_dvb_closedcaption_h

#include <lib/base/object.h>
#include <lib/dvb/idvb.h>
#include <lib/dvb/pesparse.h>
#include <lib/dvb/pmt.h>
#include <lib/gdi/gpixmap.h>
#include <map>

class eClosedCaptionParser: public iObject, public ePESParser, public sigc::trackable
{
       DECLARE_REF(eClosedCaptionParser);
public:
       eClosedCaptionParser(iDVBDemux *demux);
       virtual ~eClosedCaptionParser();
       int start(int pid);
private:
       int m_pid;
       std::map<int, unsigned int> m_modifications;
       void processPESPacket(uint8_t *pkt, int len);

       ePtr<iDVBPESReader> m_pes_reader;
       ePtr<eConnection> m_read_connection;
};

#endif
