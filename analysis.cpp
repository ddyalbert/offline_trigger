#include "TFile.h"
#include "TTree.h"
#include "TH1D.h"
#include "TCanvas.h"
#include "TGraph.h"
#include "TF1.h"
#include "TStyle.h"

#include <iostream>
#include <fstream>

void analysis()
{
    gStyle->SetOptFit(1111);
    // TString folderName = "/mnt/wsl/disk/bolometer/Data/RUN33/WTh_CS_WP_ustcBox_1121/";
    TString folderName = "/mnt/wsl/disk/bolometer/Data/RUN33/WTh_CS_WP_ustcBox_1202_4days/";
    TFile *f = new TFile(folderName + "SignalFiltered_v0.0.root", "READ");
    TTree *tree = (TTree*)f->Get("tree");

    std::ifstream inFile(".temp/fit_params.txt");
    Bool_t isSaveParams = false;
    Double_t pp[2] = {0.0, 1.0};
    if (inFile.is_open())
    {
        isSaveParams = true;
        inFile >> pp[0] >> pp[1];
    }


    Double_t Amp_fil;
    Double_t Amp_raw;
    Double_t Baseline;
    Double_t pk_interval;
    Double_t Amp_shift;
    Double_t ratio_fit;

    uint8_t isValid;

    tree->SetBranchAddress("Amp_fil", &Amp_fil);
    tree->SetBranchAddress("Amp_raw", &Amp_raw);
    tree->SetBranchAddress("Baseline", &Baseline);
    tree->SetBranchAddress("pk_interval", &pk_interval);

    tree->SetBranchAddress("isValid", &isValid);
    tree->SetBranchAddress("Amp_shift", &Amp_shift);
    tree->SetBranchAddress("ratio_fit", &ratio_fit);
    

    TH1D *h_amp   = new TH1D("amp",   "Amp (V)", 1000, 0, 8);
    TH1D *h_amp_s = new TH1D("amp_s", "Amp (V)", 40, 3.19, 3.21);

    TGraph *g1 = new TGraph();
    
    double cc = 0.02;
    int n = tree->GetEntries();
    std::cout << "num of events = " << n << std::endl;
    tree->GetEntry(0);
    for (size_t i = 0; i < n; i++)
    {
        if (pk_interval < 2) {
            tree->GetEntry(i);
            continue;
        }
        tree->GetEntry(i);
        if (pk_interval < 2) continue;
        if (!isValid) continue;
        Double_t amp = Amp_fil + Amp_shift;
        Double_t amp_s = 3.2 * amp/ (pp[0] + pp[1] * Baseline);

        h_amp->Fill(amp);
        h_amp_s->Fill(amp_s);

        if(amp < 3.1 || amp > 3.4) continue;
        if(isSaveParams){
            if (amp < pp[0] + pp[1] * Baseline - cc) continue;
            if (amp > pp[0] + pp[1] * Baseline + cc) continue;
        }
        g1->AddPoint(Baseline, amp);
    }

    // TCanvas *c = new TCanvas("c", "c");
    // h_amp->Draw();
    // h_amp->SetStats(2);

    TCanvas *c_s = new TCanvas("c_s", "c_s");
    h_amp_s->Draw();
    h_amp_s->SetStats(2);

    TF1 *guss = new TF1("guss", "[0] + [1] * TMath::Gaus(x, [2], [3])", 3.19, 3.21);
    guss->SetParNames("Constant", "Amplitude", "Mean", "Sigma");
    guss->SetParameters(0, 1, 3.25, 0.01);
    h_amp_s->Fit(guss,"R");

    TCanvas *c2 = new TCanvas("c2", "c2");
    g1->SetTitle(";Baseline (V);Amp (V)");
    g1->Draw("AP+");

    TF1 *linefit = new TF1("linefit", "[0] + [1] * x", -2.15, -1.9);
    g1->Fit(linefit);

    // std::ofstream outFile(".temp/fit_params.txt");
    // outFile << linefit->GetParameter(0) << std::endl;
    // outFile << linefit->GetParameter(1) << std::endl;
    // outFile.close();

}