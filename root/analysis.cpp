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
    TString folderName = "/mnt/wsl/disk/bolometer/Data/RUN37/";
    TFile *f = new TFile(folderName + "SignalFiltered_v0.0.root", "READ");
    TTree *tree = (TTree*)f->Get("tree");


    Double_t Amp_fil;
    Double_t Amp_raw;
    Double_t Baseline;
    Double_t pk_interval;
    Double_t Amp_shift;
    Double_t ratio_fit;
    Double_t DT;
    Double_t RT;
    Double_t chi2_fil;

    uint8_t isValid;

    tree->SetBranchAddress("Amp_fil", &Amp_fil);
    tree->SetBranchAddress("Amp_raw", &Amp_raw);
    tree->SetBranchAddress("Baseline", &Baseline);
    tree->SetBranchAddress("pk_interval", &pk_interval);
    tree->SetBranchAddress("DT", &DT);
    tree->SetBranchAddress("RT", &RT);
    tree->SetBranchAddress("chi2_fil", &chi2_fil);

    tree->SetBranchAddress("isValid", &isValid);
    tree->SetBranchAddress("Amp_shift", &Amp_shift);
    tree->SetBranchAddress("ratio_fit", &ratio_fit);
    

    TH1D *hist_amp   = new TH1D("hist_amp","Hist;Amp(V)", 300, 0, 3);
    TH1D *hist_amp_s = new TH1D("hist_amp_s", "Hist;Amp(V)", 100, 0, 3);
    TGraph *graph_stabilize = new TGraph();

    TGraph *graph_amp_RT = new TGraph();
    TGraph *graph_amp_DT = new TGraph();
    TGraph *graph_amp_chi2 = new TGraph();

    TGraph *graph_RT_DT = new TGraph();

    // stabilize fit params
    std::ifstream inFile("../.temp/fit_params.txt");
    Bool_t isSaveParams = false;
    Double_t pp[2] = {0.0, 1.0};
    if (inFile.is_open())
    {
        isSaveParams = true;
        inFile >> pp[0] >> pp[1];
    }

    double cc = 0.03;
    int n = tree->GetEntries();
    std::cout << "num of events = " << n << std::endl;
    tree->GetEntry(0);
    double min_distance = 0;
    for (size_t i = 0; i < n; i++)
    {
        if (pk_interval < min_distance) {
            tree->GetEntry(i);
            continue;
        }
        tree->GetEntry(i);
        if (pk_interval < min_distance) continue;
        if (!isValid) continue;

        if (DT < 8 || DT > 13) continue;
        if (RT < 3 || RT > 4.5) continue;
        if (chi2_fil > 0.02) continue;

        Double_t amp = Amp_fil;
        Double_t amp_s = 2.5 * amp/ (pp[0] + pp[1] * Baseline);

        hist_amp->Fill(amp);
        hist_amp_s->Fill(amp_s);

        graph_amp_RT->AddPoint(amp_s, RT);
        graph_amp_DT->AddPoint(amp_s, DT);
        graph_amp_chi2->AddPoint(amp_s, chi2_fil);

        if(amp < 2.6 || amp > 2.82) continue;
        if(isSaveParams){
            if (amp < pp[0] + pp[1] * Baseline - cc) continue;
            if (amp > pp[0] + pp[1] * Baseline + cc) continue;
        }
        // if(Baseline < -2.1 || Baseline > -1.7) continue;
        graph_stabilize->AddPoint(Baseline, amp);
    }

    // TCanvas *c_amp = new TCanvas("canvas_amp", "canvas_amp");
    // hist_amp->Draw();
    // canvas_amp->SetLogy();
    // hist_amp->SetStats(2);

    TCanvas *canvas_stab = new TCanvas("canvas_stab", "canvas_stab");
    hist_amp_s->Draw();
    canvas_stab->SetLogy();
    hist_amp_s->SetStats(2);

    // TCanvas *canvas_amp_DT = new TCanvas("canvas_amp_DT", "amp - DT");
    // graph_amp_DT->SetTitle(";Amp (V);DT (ms)");
    // graph_amp_DT->Draw("AP+");

    // TCanvas *canvas_amp_RT = new TCanvas("canvas_amp_RT", "amp - RT");
    // graph_amp_RT->SetTitle(";Amp (V);RT (ms)");
    // graph_amp_RT->Draw("AP+");

    // TCanvas *canvas_amp_chi2 = new TCanvas("canvas_amp_chi2", "amp - chi2");
    // graph_amp_chi2->SetTitle(";Amp (V);chi2");
    // graph_amp_chi2->Draw("AP+");








    // TF1 *guss = new TF1("guss", "[0] + [1] * TMath::Gaus(x, [2], [3])", 3.19, 3.21);
    // guss->SetParNames("Constant", "Amplitude", "Mean", "Sigma");
    // guss->SetParameters(0, 1, 3.25, 0.01);
    // h_amp_s->Fit(guss,"R");




    TCanvas *canvas_stablize = new TCanvas("canvas_stablize", "canvas_stablize");
    graph_stabilize->SetTitle(";Baseline (V);Amp (V)");
    graph_stabilize->SetMarkerStyle(20);
    graph_stabilize->SetMarkerSize(0.2);
    graph_stabilize->Draw("AP+");

    TF1 *linefit = new TF1("linefit", "[0] + [1] * x", -2.4, -1.8);
    graph_stabilize->Fit(linefit);

    // std::ofstream outFile("../.temp/fit_params.txt");
    // outFile << linefit->GetParameter(0) << std::endl;
    // outFile << linefit->GetParameter(1) << std::endl;
    // outFile.close();

}